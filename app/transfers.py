"""Descargas grandes por rangos, reanudables y verificadas con SHA-256."""
import hashlib
import json
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def download_weights(repo, subfolder, destination: Path, revision="main"):
    filename = "model.fp16.safetensors"
    api = f"https://huggingface.co/api/models/{repo}/tree/{revision}/{subfolder}"
    with urllib.request.urlopen(api, timeout=60) as response:
        files = json.load(response)
    metadata = next(item for item in files if item["path"] == f"{subfolder}/{filename}")
    total = metadata["size"]
    expected_hash = metadata["lfs"]["oid"]
    url = f"https://huggingface.co/{repo}/resolve/{revision}/{subfolder}/{filename}"
    return download_ranges(url, total, expected_hash, destination)


def download_ranges(url, total, expected_hash, destination: Path):
    chunk_size = 16 * 1024 * 1024
    chunks = (total + chunk_size - 1) // chunk_size
    parts = destination.with_name(destination.name + ".chunks")
    parts.mkdir(parents=True, exist_ok=True)
    # Aprovecha una descarga secuencial interrumpida si existe.
    sequential = destination.with_name(destination.name + ".part")
    if sequential.exists():
        available = sequential.stat().st_size
        with sequential.open("rb") as source:
            for index in range(min(available // chunk_size, chunks)):
                path = parts / str(index)
                if not path.exists():
                    source.seek(index * chunk_size)
                    path.write_bytes(source.read(chunk_size))

    def fetch(index):
        start = index * chunk_size
        end = min(total - 1, start + chunk_size - 1)
        path = parts / str(index)
        length = end - start + 1
        if path.exists() and path.stat().st_size == length:
            return length
        for attempt in range(6):
            try:
                request = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
                with urllib.request.urlopen(request, timeout=90) as response:
                    if response.status != 206 or response.headers.get("Content-Range") != f"bytes {start}-{end}/{total}":
                        raise OSError("El servidor no devolvió el rango solicitado")
                    with path.with_suffix(".tmp").open("wb") as output:
                        read = 0
                        while block := response.read(1024 * 1024):
                            output.write(block)
                            read += len(block)
                    if read != length:
                        raise OSError("Fragmento incompleto")
                path.with_suffix(".tmp").replace(path)
                return length
            except Exception:
                if attempt == 5:
                    raise
                time.sleep(min(2 ** attempt, 10))

    completed = 0
    last_report = -1
    with ThreadPoolExecutor(max_workers=8) as pool:
        for result in as_completed([pool.submit(fetch, index) for index in range(chunks)]):
            completed += result.result()
            percent = int(completed * 100 / total)
            if percent // 5 != last_report // 5:
                print(f"Descargando pesos: {percent}%", flush=True)
                last_report = percent
    digest = hashlib.sha256()
    combined = destination.with_name(destination.name + ".verified-part")
    with combined.open("wb") as output:
        for index in range(chunks):
            with (parts / str(index)).open("rb") as source:
                while block := source.read(4 * 1024 * 1024):
                    digest.update(block)
                    output.write(block)
    if digest.hexdigest() != expected_hash:
        raise OSError("El SHA-256 de los pesos no coincide. No se usará el archivo descargado.")
    combined.replace(destination)
    for index in range(chunks):
        (parts / str(index)).unlink()
    parts.rmdir()
    if sequential.exists():
        sequential.unlink()
    print(f"Pesos verificados: SHA-256 {expected_hash}", flush=True)
