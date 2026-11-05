"""Un proceso por generación libera la VRAM al finalizar o cancelar."""
import json
import sys
import time
import traceback
from pathlib import Path

from app.config import MODELS, QUALITIES, VENDOR, configure_environment, model_directory


def event(progress, stage, **extra):
    print("GENSTL:" + json.dumps({"progress": progress, "stage": stage, **extra}), flush=True)


def run(folder: Path):
    configure_environment()
    sys.path.insert(0, str(VENDOR))
    event(2, "Iniciando motor de IA")
    import torch
    from PIL import Image
    from app.engine import load_pipeline
    from app.mesh import export_mesh

    if not torch.cuda.is_available():
        raise RuntimeError("No se detectó CUDA. Ejecuta instalar.ps1 para instalar PyTorch con CUDA.")
    job = json.loads((folder / "job.json").read_text(encoding="utf-8"))
    opts = job["options"]
    started = time.monotonic()
    images = {}
    event(5, "Preparando imágenes")
    session = None
    for view in job["views"]:
        image = Image.open(folder / f"{view}.png").convert("RGBA")
        if opts["remove_background"] and image.getextrema()[3][0] == 255:
            event(7, "Quitando fondo (la primera vez descarga el segmentador)")
            from rembg import new_session, remove
            if session is None:
                session = new_session("u2netp", providers=["CPUExecutionProvider"])
            image = remove(image, session=session)
        if image.getchannel("A").getbbox() is None:
            raise ValueError("La imagen quedó transparente. Desactiva Quitar fondo o usa otra foto.")
        image.save(folder / f"prepared_{view}.png")
        images[view] = image
    del session

    engine = job["engine"]
    directory = model_directory(engine)
    if not (directory / "model.fp16.safetensors").is_file():
        event(10, "Descargando modelo de IA; puede tardar varios minutos")
        from app.download import download_model
        download_model(engine)
    event(20, "Cargando modelo en memoria")
    # Motor original intacto; carga por mapeo de memoria y asignación de pesos.
    pipeline = load_pipeline(engine)
    # Etapas explícitas: el método offload del upstream no define components.
    # Encoder, DiT y VAE ocupan la GPU por turnos para reducir el pico de VRAM.
    encode = pipeline.encode_cond
    export = pipeline._export

    def staged_encode(*args, **kwargs):
        pipeline.conditioner.to("cuda")
        result = encode(*args, **kwargs)
        pipeline.conditioner.to("cpu")
        torch.cuda.empty_cache()
        pipeline.model.to("cuda")
        return result

    def staged_export(*args, **kwargs):
        event(78, "Extrayendo superficie 3D")
        pipeline.model.to("cpu")
        torch.cuda.empty_cache()
        pipeline.vae.to("cuda")
        return export(*args, **kwargs)

    pipeline.encode_cond = staged_encode
    pipeline._export = staged_export
    pipeline.device = torch.device("cuda")
    quality = QUALITIES[opts["quality"]]
    steps = quality["steps"] if engine == "mini" else {"draft": 20, "standard": 30, "high": 50}[opts["quality"]]

    def callback(step, *_):
        event(30 + int(45 * (step + 1) / steps), f"Generando geometría · paso {step + 1}/{steps}")

    event(28, "Analizando las vistas del objeto")
    with torch.inference_mode():
        mesh = pipeline(
            image=images if engine == "multiview" else next(iter(images.values())),
            num_inference_steps=steps, octree_resolution=quality["resolution"],
            num_chunks=2048, guidance_scale=5.0,
            generator=torch.Generator(device="cuda").manual_seed(opts["seed"]),
            output_type="trimesh", mc_algo="mc", enable_pbar=False,
            callback=callback, callback_steps=1,
        )[0]
    if mesh is None:
        raise RuntimeError("No se pudo extraer la superficie. Prueba otra imagen o semilla.")
    event(92, "Limpiando y exportando archivos")
    stats = export_mesh(mesh, folder, opts["size_mm"])
    stats["generation_seconds"] = round(time.monotonic() - started, 1)
    stats["engine"] = engine
    (folder / "result.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    event(100, "Modelo listo", stats=stats)


if __name__ == "__main__":
    try:
        run(Path(sys.argv[1]).resolve())
    except Exception as error:
        traceback.print_exc()
        message = str(error)
        if "out of memory" in message.lower():
            message = "La GPU se quedó sin memoria. Cierra otras apps, usa calidad Borrador o una sola imagen."
        elif len(message) > 500:
            message = message.splitlines()[0] + " Consulta worker.log en la carpeta del trabajo para ver el detalle."
        event(0, "Error", error=message)
        sys.exit(1)
