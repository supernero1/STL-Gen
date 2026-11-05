import importlib.metadata
import io
import json
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import FORMATS, QUALITIES, ROOT, VENDOR, VIEWS, model_directory
from app.jobs import JobManager

Image.MAX_IMAGE_PIXELS = 16_777_216


@asynccontextmanager
async def lifespan(app):
    app.state.jobs = JobManager()
    yield
    app.state.jobs.close()


app = FastAPI(title="Gen STL Studio", version="1.0.0", lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])


@app.middleware("http")
async def local_requests(request, call_next):
    origin = request.headers.get("origin")
    if request.method not in ("GET", "HEAD", "OPTIONS") and origin and origin != str(request.base_url).rstrip("/"):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Origen no permitido"}, status_code=403)
    return await call_next(request)


def manager():
    return app.state.jobs


def require_job(job_id):
    job = manager().get(job_id)
    if not job:
        raise HTTPException(404, "Trabajo no encontrado")
    return job


@app.get("/api/system")
def system():
    try:
        info = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"],
            text=True, timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).strip().splitlines()[0].split(",")
        gpu = {"name": info[0].strip(), "total_mb": int(info[1]), "free_mb": int(info[2])}
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        gpu = None
    dependencies = {}
    for package in ("torch", "diffusers", "transformers", "rembg"):
        try:
            dependencies[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            dependencies[package] = None
    ready = bool(gpu and all(dependencies.values()) and "+cu" in (dependencies["torch"] or "") and (VENDOR / "hy3dgen").is_dir())
    return {
        "gpu": gpu, "dependencies": dependencies, "ready": ready,
        "models": {key: (model_directory(key) / "model.fp16.safetensors").is_file() for key in ("mini", "multiview")},
    }


@app.get("/api/jobs")
def list_jobs():
    return manager().list()


@app.post("/api/jobs", status_code=202)
async def create_job(
    images: list[UploadFile] = File(...), views: str = Form(...),
    quality: str = Form("draft"), size_mm: float = Form(100, ge=5, le=1000),
    seed: int = Form(12345, ge=0, le=2_147_483_647),
    remove_background: bool = Form(True), name: str = Form("Mi modelo"),
):
    if quality not in QUALITIES:
        raise HTTPException(422, "Calidad no válida")
    try:
        view_list = json.loads(views)
    except ValueError:
        raise HTTPException(422, "Vistas no válidas")
    if not isinstance(view_list, list) or not 1 <= len(images) <= 4 or len(images) != len(view_list):
        raise HTTPException(422, "Carga de una a cuatro imágenes y asigna sus vistas")
    if any(not isinstance(v, str) or v not in VIEWS for v in view_list) or len(set(view_list)) != len(view_list):
        raise HTTPException(422, "Cada vista debe ser válida y única")
    if "front" not in view_list:
        raise HTTPException(422, "Incluye una vista frontal")
    decoded = {}
    for view, upload in zip(view_list, images):
        content = await upload.read(15 * 1024 * 1024 + 1)
        if len(content) > 15 * 1024 * 1024:
            raise HTTPException(413, "Cada imagen debe pesar menos de 15 MB")
        try:
            with Image.open(io.BytesIO(content)) as image:
                if image.format not in ("PNG", "JPEG", "WEBP") or getattr(image, "is_animated", False):
                    raise ValueError("Usa PNG, JPG o WebP estático")
                if min(image.size) < 64 or max(image.size) > 4096 or image.width * image.height > Image.MAX_IMAGE_PIXELS:
                    raise ValueError("La imagen debe medir entre 64 y 4096 píxeles por lado")
                image.load()
                decoded[view] = ImageOps.exif_transpose(image).convert("RGBA")
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as error:
            raise HTTPException(422, f"Imagen no válida: {error}")
    options = dict(quality=quality, size_mm=size_mm, seed=seed, remove_background=remove_background)
    try:
        return manager().create(decoded, options, name.strip() or "Mi modelo")
    except ValueError as error:
        raise HTTPException(429, str(error))


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    return require_job(job_id)


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    require_job(job_id)
    return manager().cancel(job_id)


@app.get("/api/jobs/{job_id}/image/{view}")
def input_image(job_id: str, view: str):
    job = require_job(job_id)
    if view not in job["views"]:
        raise HTTPException(404)
    return FileResponse(manager().root / job_id / f"{view}.png", media_type="image/png")


@app.get("/api/jobs/{job_id}/model/{fmt}")
def download(job_id: str, fmt: str, inline: bool = False):
    job = require_job(job_id)
    if fmt not in FORMATS:
        raise HTTPException(422, "Formato no compatible")
    if job["status"] != "completed":
        raise HTTPException(409, "El modelo todavía no está listo")
    path = manager().root / job_id / f"model.{fmt}"
    if not path.is_file():
        raise HTTPException(404, "Archivo no disponible")
    return FileResponse(path, filename=f"gen-stl-{job_id[:8]}.{fmt}",
                        content_disposition_type="inline" if inline else "attachment",
                        media_type="model/gltf-binary" if fmt == "glb" else "application/octet-stream")


@app.get("/")
def index():
    return FileResponse(ROOT / "web" / "index.html")


app.mount("/static", StaticFiles(directory=ROOT / "web"), name="static")
three = ROOT / "node_modules" / "three"
if three.is_dir():
    app.mount("/three", StaticFiles(directory=three), name="three")
