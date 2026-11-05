"""Instala la rueda CUDA oficial con descarga reanudable e integridad verificada."""
import hashlib
import importlib.metadata
import subprocess
import sys
from pathlib import Path

from app.config import CACHE
from app.transfers import download_ranges

TORCH_SHA256 = "3313061c1fec4c7310cf47944e84513dcd27b6173b72a349bb7ca68d0ee6e9c0"


if __name__ == "__main__":
    if sys.platform != "win32" or sys.version_info[:2] != (3, 12):
        raise SystemExit("Este instalador está preparado para Windows x64 y Python 3.12.")
    try:
        installed = importlib.metadata.version("torch")
    except importlib.metadata.PackageNotFoundError:
        installed = None
    if installed != "2.6.0+cu124":
        wheel = CACHE / "wheels" / "torch-2.6.0+cu124-cp312-cp312-win_amd64.whl"
        wheel.parent.mkdir(parents=True, exist_ok=True)
        valid = False
        if wheel.is_file() and wheel.stat().st_size == 2532302369:
            with wheel.open("rb") as source:
                valid = hashlib.file_digest(source, "sha256").hexdigest() == TORCH_SHA256
        if not valid:
            download_ranges(
                "https://download.pytorch.org/whl/cu124/torch-2.6.0%2Bcu124-cp312-cp312-win_amd64.whl",
                2532302369, TORCH_SHA256, wheel,
            )
        subprocess.run([sys.executable, "-m", "pip", "install", str(wheel), "--timeout", "120"], check=True)
    try:
        vision_installed = importlib.metadata.version("torchvision")
    except importlib.metadata.PackageNotFoundError:
        vision_installed = None
    if vision_installed != "0.21.0+cu124":
        subprocess.run([
            sys.executable, "-m", "pip", "install", "torchvision==0.21.0+cu124",
            "--index-url", "https://download.pytorch.org/whl/cu124", "--timeout", "120",
        ], check=True)
