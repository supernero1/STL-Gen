"""Diagnóstico breve del entorno instalado."""
if __name__ == "__main__":
    import torch
    from app.config import VENDOR
    import sys
    sys.path.insert(0, str(VENDOR))
    from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline

    print("PyTorch:", torch.__version__)
    print("CUDA:", torch.cuda.is_available())
    if not torch.cuda.is_available():
        raise SystemExit("No se encontró una GPU CUDA compatible.")
    print("GPU:", torch.cuda.get_device_name(0))
    print("Motor Hunyuan3D importado correctamente")
