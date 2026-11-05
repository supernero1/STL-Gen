"""Exportación consistente: impresión en mm/Z arriba, GLB en m/Y arriba."""
from pathlib import Path

import numpy as np
import trimesh


def depth_analysis(dimensions_mm):
    """Heurística en los ejes de exportación: X ancho, Y fondo, Z alto.

    Un objeto delgado puede ser intencional. Esto informa; no deforma la malla
    ni garantiza que una forma más gruesa sea anatómicamente correcta.
    """
    width, depth, height = map(float, dimensions_mm)
    reference = max(width, height)
    ratio = depth / reference if reference > 0 else 0.0
    return {"depth_ratio": round(ratio, 4), "low_depth": ratio < 0.12}


def export_mesh(mesh: trimesh.Trimesh, folder: Path, size_mm: float):
    mesh = mesh.copy()
    mesh.process(validate=True)
    mesh.remove_unreferenced_vertices()
    if not len(mesh.faces) or not np.isfinite(mesh.vertices).all():
        raise ValueError("La IA no produjo una malla válida. Prueba otra imagen o semilla.")
    # Normalizar al eje mayor solicitado, sin inventar medidas desde la foto.
    extent = float(max(mesh.extents))
    if extent <= 0:
        raise ValueError("El modelo no tiene volumen espacial.")
    mesh.apply_translation(-mesh.bounds.mean(axis=0))
    mesh.apply_scale(size_mm / extent)
    trimesh.repair.fix_normals(mesh, multibody=True)
    trimesh.repair.fill_holes(mesh)

    printable = mesh.copy()
    printable.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    printable.apply_translation([0, 0, -printable.bounds[0, 2]])
    printable.units = "mm"
    folder.mkdir(parents=True, exist_ok=True)
    for fmt in ("stl", "obj", "ply"):
        printable.export(folder / f"model.{fmt}", file_type=fmt)
    preview = mesh.copy()
    preview.apply_scale(0.001)
    preview.units = "m"
    preview.export(folder / "model.glb", file_type="glb", include_normals=True)
    dimensions = np.round(printable.extents, 2).tolist()
    return {
        "vertices": len(mesh.vertices),
        "faces": len(mesh.faces),
        "watertight": bool(mesh.is_watertight),
        "dimensions_mm": dimensions,
        **depth_analysis(dimensions),
        "units": "mm (STL/OBJ/PLY), m (GLB)",
    }
