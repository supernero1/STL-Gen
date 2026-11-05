import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("GEN_STL_DATA", ROOT / "data"))
JOBS = DATA / "jobs"
CACHE = ROOT / ".cache"
VENDOR = ROOT / "vendor" / "Hunyuan3D-2"
MODELS = {
    "mini": ("tencent/Hunyuan3D-2mini", "hunyuan3d-dit-v2-mini-turbo"),
    "multiview": ("tencent/Hunyuan3D-2mv", "hunyuan3d-dit-v2-mv"),
}
MODEL_REVISIONS = {
    "mini": "f90a0f7df7d5e6f71109cf333f6a95a0ae3194a6",
    "multiview": "3a761b539b29fe4ff64714813aa9560fd66f5de0",
}
QUALITIES = {
    "draft": {"steps": 5, "resolution": 128},
    "standard": {"steps": 8, "resolution": 192},
    "high": {"steps": 12, "resolution": 256},
}
VIEWS = ("front", "left", "back", "right")
FORMATS = ("stl", "obj", "glb", "ply")


def configure_environment():
    for key, value in {
        "HF_HOME": CACHE / "huggingface",
        "HY3DGEN_MODELS": CACHE / "models",
        "U2NET_HOME": CACHE / "rembg",
        "TORCH_HOME": CACHE / "torch",
    }.items():
        os.environ[key] = str(value)
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"


def model_directory(engine):
    repo, subfolder = MODELS[engine]
    return CACHE / "models" / repo / subfolder
