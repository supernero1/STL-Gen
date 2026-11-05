"""Descarga únicamente configuración, pesos FP16 y licencias oficiales."""
import argparse
from app.config import CACHE, MODELS, MODEL_REVISIONS, configure_environment, model_directory


def download_model(engine):
    configure_environment()
    from huggingface_hub import hf_hub_download
    repo, subfolder = MODELS[engine]
    target = CACHE / "models" / repo
    for filename in ("config.yaml",):
        hf_hub_download(repo, filename=f"{subfolder}/{filename}", local_dir=target, revision=MODEL_REVISIONS[engine])
    weights = model_directory(engine) / "model.fp16.safetensors"
    if not weights.is_file():
        from app.transfers import download_weights
        download_weights(repo, subfolder, weights, MODEL_REVISIONS[engine])
    hf_hub_download(repo, filename="LICENSE", local_dir=target, revision=MODEL_REVISIONS[engine])
    return model_directory(engine)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", choices=MODELS, default="mini")
    args = parser.parse_args()
    print(download_model(args.engine))
