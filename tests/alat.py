"""Alat bantu uji: jalankan CLI, buat repo git sementara, server HTTP lokal."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def jalankan_cli(*argumen, cwd=None):
    """Jalankan `python3 -m sidik_jari ...`, kembalikan CompletedProcess."""
    return subprocess.run(
        [sys.executable, "-m", "sidik_jari", *[str(a) for a in argumen]],
        capture_output=True, text=True, timeout=120, cwd=cwd or ROOT,
    )


def tulis(path, data: bytes) -> str:
    with open(path, "wb") as f:
        f.write(data)
    return path


def buat_repo(dirpath: str) -> str:
    """Buat repo git sementara dengan satu commit (user lokal, tanpa gpg)."""
    dirpath = str(dirpath)
    subprocess.run(["git", "init", dirpath], check=True, capture_output=True)
    for kunci, nilai in (("user.name", "uji"), ("user.email", "uji@uji")):
        subprocess.run(["git", "-C", dirpath, "config", kunci, nilai],
                       check=True, capture_output=True)
    tulis(os.path.join(dirpath, "berkas.txt"), b"halo repo uji")
    subprocess.run(["git", "-C", dirpath, "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", dirpath, "-c", "commit.gpgsign=false",
                    "commit", "-m", "commit uji"], check=True, capture_output=True)
    return dirpath


class _Penangan(BaseHTTPRequestHandler):
    def do_GET(self):
        pasangan = getattr(self.server, "respons", {}).get(self.path)
        if pasangan is None:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        status, body, kepala = pasangan
        self.send_response(status)
        for kunci, nilai in (kepala or {}).items():
            self.send_header(kunci, nilai)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # bisukan log server uji


class ServerUji:
    """Server HTTP lokal di thread; respons diatur per path."""

    def __init__(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Penangan)
        self.server.respons = {}
        self.latar = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.latar.start()

    @property
    def port(self) -> int:
        return self.server.server_address[1]

    def url(self, path: str = "/") -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def setel(self, path: str, body: bytes = b"", status: int = 200, kepala=None):
        self.server.respons[path] = (status, body, kepala)

    def henti(self):
        self.server.shutdown()
        self.server.server_close()
