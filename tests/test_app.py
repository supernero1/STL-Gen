import io
import json
import struct
from unittest.mock import patch

import numpy as np
import pytest
import trimesh
from fastapi.testclient import TestClient
from PIL import Image

from app.jobs import JobManager
from app.main import app
from app.mesh import export_mesh, depth_analysis


def png(size=(128, 128)):
    content = io.BytesIO()
    Image.new("RGBA", size, (90, 140, 50, 255)).save(content, format="PNG")
    return content.getvalue()


@pytest.fixture
def client(tmp_path):
    with patch("app.main.JobManager", lambda: JobManager(tmp_path)), patch.object(JobManager, "run"):
        with TestClient(app) as client:
            yield client


def submit(client, views=None, count=1, **extra):
    data = {"views": json.dumps(views or ["front"]), **extra}
    return client.post("/api/jobs", data=data, files=[("images", (f"image{i}.png", png(), "image/png")) for i in range(count)])


def test_upload_saved_and_multiview_selected(client):
    response = submit(client, views=["front", "left", "back"], count=3, size_mm=85, seed=32)
    assert response.status_code == 202
    job = response.json()
    assert job["engine"] == "multiview"
    assert job["options"]["size_mm"] == 85
    assert client.get(f'/api/jobs/{job["id"]}/image/back').status_code == 200
    assert client.get("/api/jobs").json()[0]["id"] == job["id"]
    assert client.get(f'/api/jobs/{job["id"]}/model/stl').status_code == 409


@pytest.mark.parametrize("views,count", [(["front", "front"], 2), (["left"], 1), (["front", "../../other"], 2), (["front"], 2), ([{}], 1)])
def test_invalid_views_rejected(client, views, count):
    assert submit(client, views, count).status_code == 422
    assert client.get("/api/jobs").json() == []


def test_invalid_images_and_numbers_rejected(client):
    response = client.post("/api/jobs", data={"views": '["front"]'}, files={"images": ("fake.png", b"not an image", "image/png")})
    assert response.status_code == 422
    response = client.post("/api/jobs", data={"views": '["front"]'}, files={"images": ("tiny.png", png((32, 32)), "image/png")})
    assert response.status_code == 422
    assert submit(client, size_mm=-5).status_code == 422
    assert submit(client, seed=-1).status_code == 422


def test_cancel_and_persistence(client):
    job = submit(client).json()
    job_id = job["id"]
    assert client.post(f"/api/jobs/{job_id}/cancel").json()["status"] == "cancelled"
    assert client.post(f"/api/jobs/{job_id}/cancel").status_code == 200
    restored = JobManager(app.state.jobs.root)
    try:
        assert restored.get(job_id)["status"] == "cancelled"
    finally:
        restored.close()


def test_interrupted_job_marked_failed_on_restart(tmp_path):
    first = JobManager(tmp_path)
    with patch.object(first, "run"):
        job = first.create({"front": Image.new("RGBA", (100, 100))}, {}, "Prueba")
    first.close()
    restored = JobManager(tmp_path)
    assert restored.get(job["id"])["status"] == "failed"
    restored.close()


def test_export_formats_scale_axis_and_download(client, tmp_path):
    # Malla asimétrica: la rotación de ejes y la escala se verifican al releer archivos.
    mesh = trimesh.creation.box(extents=[1, 2, 3])
    stats = export_mesh(mesh, tmp_path, 120)
    stl = trimesh.load(tmp_path / "model.stl", force="mesh")
    glb = trimesh.load(tmp_path / "model.glb", force="mesh")
    payload = (tmp_path / "model.glb").read_bytes()
    gltf = json.loads(payload[20:20 + struct.unpack_from("<I", payload, 12)[0]])
    assert "NORMAL" in gltf["meshes"][0]["primitives"][0]["attributes"]
    obj = trimesh.load(tmp_path / "model.obj", force="mesh")
    ply = trimesh.load(tmp_path / "model.ply", force="mesh")
    np.testing.assert_allclose(stl.extents, [40, 120, 80], atol=.001)
    np.testing.assert_allclose(obj.extents, stl.extents, atol=.001)
    np.testing.assert_allclose(ply.extents, stl.extents, atol=.001)
    np.testing.assert_allclose(glb.extents, [.04, .08, .12], atol=.00001)
    assert abs(stl.bounds[0, 2]) < .001
    assert stats["watertight"]
    job = submit(client).json()
    folder = app.state.jobs.root / job["id"]
    export_mesh(mesh, folder, 120)
    app.state.jobs.update(job["id"], status="completed", stats=stats)
    for fmt in ("stl", "obj", "glb", "ply"):
        response = client.get(f'/api/jobs/{job["id"]}/model/{fmt}')
        assert response.status_code == 200
        assert len(response.content) > 100
    assert client.get(f'/api/jobs/{job["id"]}/model/exe').status_code == 422


def test_cross_origin_write_blocked(client):
    assert client.post("/api/jobs/fake/cancel", headers={"origin": "https://example.com"}).status_code == 403


def test_app_serves_local_assets(client):
    assert client.get("/").status_code == 200
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/three/build/three.module.js").status_code == 200


def test_closed_thin_model_flagged_without_stretching(tmp_path):
    # Ser watertight no prueba que una figura tenga volumen suficiente.
    thin = trimesh.creation.box(extents=[.88, 1, .0258])
    stats = export_mesh(thin, tmp_path, 100)
    assert stats["watertight"]
    assert stats["low_depth"]
    assert stats["depth_ratio"] == .0258
    exported = trimesh.load(tmp_path / "model.stl", force="mesh")
    np.testing.assert_allclose(exported.extents, [88, 2.58, 100], atol=.001)
    assert not depth_analysis([65, 50, 100])["low_depth"]
