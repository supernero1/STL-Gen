"""Carga los pesos oficiales sin duplicar varios GB de parámetros en RAM."""
from app.config import model_directory


def load_pipeline(engine):
    import torch
    import yaml
    from accelerate import init_empty_weights
    from safetensors import safe_open
    from hy3dgen.shapegen.pipelines import Hunyuan3DDiTFlowMatchingPipeline, instantiate_from_config

    directory = model_directory(engine)
    config = yaml.safe_load((directory / "config.yaml").read_text(encoding="utf-8"))
    components = {}
    with safe_open(str(directory / "model.fp16.safetensors"), framework="pt", device="cpu") as checkpoint:
        for name in ("model", "vae", "conditioner"):
            # Sólo parámetros en meta; los buffers no persistentes se crean en CPU.
            with init_empty_weights(include_buffers=False):
                component = instantiate_from_config(config[name])
            prefix = name + "."
            weights = {key[len(prefix):]: checkpoint.get_tensor(key) for key in checkpoint.keys() if key.startswith(prefix)}
            if not weights:
                raise ValueError(f"El checkpoint no contiene el componente {name}")
            if name == "vae":
                # Estos checkpoints de generación sólo publican el decodificador.
                # El encoder de nubes de puntos se utiliza para entrenamiento/encode,
                # no para generar una malla a partir de los latentes del DiT.
                for unused in ("encoder", "pre_kl"):
                    if not any(key.startswith(unused + ".") for key in weights):
                        setattr(component, unused, None)
            component.load_state_dict(weights, assign=True, strict=True)
            if any(parameter.is_meta for parameter in component.parameters()):
                raise ValueError(f"Carga incompleta del componente {name}")
            component.eval()
            components[name] = component
    components["scheduler"] = instantiate_from_config(config["scheduler"])
    components["image_processor"] = instantiate_from_config(config["image_processor"])
    return Hunyuan3DDiTFlowMatchingPipeline(**components, device="cpu", dtype=torch.float16)
