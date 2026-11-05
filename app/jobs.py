import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.config import JOBS, ROOT


def terminate_process(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        # El redirector de Python de un venv en Windows crea un proceso hijo.
        # Hay que detener el árbol para liberar también su memoria CUDA.
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False)
    else:
        process.terminate()


class JobManager:
    def __init__(self, root: Path = JOBS):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gen-stl")
        self.processes = {}
        self.jobs = {}
        for path in self.root.glob("*/job.json"):
            try:
                job = json.loads(path.read_text(encoding="utf-8"))
                if job["status"] in ("queued", "running"):
                    job.update(status="failed", stage="La app se cerró durante la generación", error="Vuelve a generar el modelo.")
                self.jobs[job["id"]] = job
                self.save(job)
            except (ValueError, KeyError, OSError):
                continue

    def save(self, job):
        path = self.root / job["id"] / "job.json"
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)

    def update(self, job_id, **values):
        with self.lock:
            job = self.jobs[job_id]
            job.update(values)
            self.save(job)

    def create(self, images, options, name):
        with self.lock:
            if sum(j["status"] in ("queued", "running") for j in self.jobs.values()) >= 4:
                raise ValueError("La cola está llena. Espera a que termine un trabajo.")
            job_id = uuid4().hex
            folder = self.root / job_id
            folder.mkdir()
            for view, image in images.items():
                image.save(folder / f"{view}.png")
            job = {
                "id": job_id, "name": name[:80], "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "queued", "progress": 0, "stage": "Esperando turno",
                "engine": "mini" if len(images) == 1 else "multiview",
                "views": list(images), "options": options, "stats": None, "error": None,
            }
            self.jobs[job_id] = job
            self.save(job)
            self.pool.submit(self.run, job_id)
            return dict(job)

    def run(self, job_id):
        folder = self.root / job_id
        with self.lock:
            if self.jobs[job_id]["status"] == "cancelled":
                return
            self.update(job_id, status="running", stage="Iniciando generación")
            env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
            try:
                process = subprocess.Popen(
                    [sys.executable, "-m", "app.worker", str(folder)], cwd=ROOT,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                    env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except OSError as error:
                self.update(job_id, status="failed", error=str(error), stage="No se pudo iniciar el motor")
                return
            self.processes[job_id] = process
        try:
            with (folder / "worker.log").open("w", encoding="utf-8") as log:
                for line in process.stdout:
                    log.write(line)
                    log.flush()
                    if line.startswith("GENSTL:"):
                        try:
                            values = json.loads(line[7:])
                            with self.lock:
                                if self.jobs[job_id]["status"] != "cancelled":
                                    self.update(job_id, **values)
                        except ValueError:
                            continue
            code = process.wait()
            with self.lock:
                if self.jobs[job_id]["status"] == "cancelled":
                    return
                if code == 0 and (folder / "result.json").exists():
                    self.update(job_id, status="completed", progress=100, stage="Modelo listo")
                else:
                    error = self.jobs[job_id].get("error") or "El motor se detuvo. Consulta worker.log en la carpeta del trabajo."
                    self.update(job_id, status="failed", error=error, stage="No se pudo generar")
        except Exception as error:
            terminate_process(process)
            process.wait()
            self.update(job_id, status="failed", error=str(error), stage="Error del motor")
        finally:
            with self.lock:
                self.processes.pop(job_id, None)

    def cancel(self, job_id):
        with self.lock:
            job = self.jobs[job_id]
            if job["status"] in ("queued", "running"):
                self.update(job_id, status="cancelled", stage="Cancelado")
                process = self.processes.get(job_id)
                if process and process.poll() is None:
                    terminate_process(process)
            return dict(job)

    def list(self):
        with self.lock:
            return sorted((dict(j) for j in self.jobs.values()), key=lambda j: j["created_at"], reverse=True)

    def get(self, job_id):
        with self.lock:
            return dict(self.jobs[job_id]) if job_id in self.jobs else None

    def close(self):
        with self.lock:
            for process in self.processes.values():
                if process.poll() is None:
                    terminate_process(process)
        self.pool.shutdown(wait=True, cancel_futures=True)
