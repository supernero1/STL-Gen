import socket
import threading
import time
import urllib.request
import webbrowser

import uvicorn

URL = "http://127.0.0.1:7860"


def open_when_ready():
    for _ in range(60):
        try:
            with urllib.request.urlopen(URL, timeout=1) as response:
                if response.status == 200:
                    webbrowser.open(URL)
                    return
        except OSError:
            time.sleep(0.5)


if __name__ == "__main__":
    with socket.socket() as probe:
        occupied = probe.connect_ex(("127.0.0.1", 7860)) == 0
    if occupied:
        try:
            import json
            with urllib.request.urlopen(URL + "/openapi.json", timeout=2) as response:
                existing = json.load(response)
            if existing.get("info", {}).get("title") == "Gen STL Studio":
                webbrowser.open(URL)
            else:
                raise RuntimeError("El puerto 7860 esta ocupado por otra aplicacion.")
        except Exception as error:
            raise SystemExit(str(error))
    else:
        print("Gen STL Studio: " + URL)
        print("Deja esta ventana abierta. Pulsa Ctrl+C para detener la app.")
        threading.Thread(target=open_when_ready, daemon=True).start()
        uvicorn.run("app.main:app", host="127.0.0.1", port=7860, log_level="info", access_log=False)
