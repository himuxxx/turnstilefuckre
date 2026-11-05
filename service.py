import os
import platform
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from typing import Optional
import json

from solver import solve


PORT = int(os.environ.get("PORT", 8191))
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", 4))

HOST = os.environ.get("HOST", "0.0.0.0")

_worker_sem = threading.Semaphore(MAX_WORKERS)
_active_count = 0
_queued_count = 0
_count_lock = threading.Lock()


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True 


def _ensure_display() -> Optional[subprocess.Popen]:
    if platform.system() != "Linux":
        return None
    if os.environ.get("DISPLAY"):
        return None
    xvfb = subprocess.Popen(
        ["Xvfb", ":99", "-screen", "0", "1280x900x24"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    os.environ["DISPLAY"] = ":99"
    time.sleep(0.5)
    print("[service] started Xvfb on :99")
    return xvfb


class Handler(BaseHTTPRequestHandler):
    def send_json(self, code: int, data: dict):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")  
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):        
        client_ip = self.address_string()
        print(f"[service] {client_ip} - {fmt % args}")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        if self.path != "/solve":
            self.send_json(404, {"error": "not found — use POST /solve"})
            return

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            self.send_json(400, {"error": "invalid JSON"})
            return

        sitekey = payload.get("sitekey", "").strip()
        siteurl = payload.get("siteurl", "").strip()
        timeout = int(payload.get("timeout", 45))

        if not sitekey or not siteurl:
            self.send_json(400, {"error": "sitekey and siteurl are required"})
            return

        global _active_count, _queued_count

        with _count_lock:
            _queued_count += 1
        print(f"[service] queued — sitekey={sitekey!r} url={siteurl!r} "
              f"(active={_active_count}/{MAX_WORKERS} queued={_queued_count})")

        _worker_sem.acquire()

        with _count_lock:
            _queued_count -= 1
            _active_count += 1

        t0 = time.time()
        try:
            print(f"[service] solving sitekey={sitekey!r} url={siteurl!r} "
                  f"(active={_active_count}/{MAX_WORKERS})")
            token = solve(sitekey, siteurl, timeout=timeout)
            elapsed = round(time.time() - t0, 2)
            print(f"[service] solved in {elapsed}s  token={token[:20]}...")
            self.send_json(200, {"token": token, "elapsed": elapsed})
        except Exception as exc:
            elapsed = round(time.time() - t0, 2)
            print(f"[service] error after {elapsed}s: {exc}")
            self.send_json(500, {"error": str(exc)})
        finally:
            with _count_lock:
                _active_count -= 1
            _worker_sem.release()

    def do_GET(self):
        if self.path == "/health":
            with _count_lock:
                self.send_json(200, {
                    "status": "ok",
                    "workers": MAX_WORKERS,
                    "active": _active_count,
                    "queued": _queued_count,
                    "host": HOST,
                    "port": PORT,
                })
        elif self.path == "/":
            self.send_json(200, {
                "service": "Turnstile Solver",
                "endpoints": {
                    "POST /solve": {"sitekey": "string", "siteurl": "string", "timeout": "int (optional)"},
                    "GET /health": "status check",
                    "GET /": "this info"
                }
            })
        else:
            self.send_json(404, {"error": "use POST /solve or GET /health"})


def get_public_ip():
    try:
        import requests
        response = requests.get('https://api.ipify.org?format=json', timeout=5)
        return response.json().get('ip')
    except:
        return "unknown"


if __name__ == "__main__":
    xvfb_proc = _ensure_display()

    public_ip = get_public_ip()
    
    server = ThreadedHTTPServer((HOST, PORT), Handler)
    print("=" * 60)
    print("[service] 🚀 Turnstile Solver Service")
    print("=" * 60)
    print(f"[service] 📡 Local:  http://{HOST}:{PORT}")
    print(f"[service] 🌐 Public: http://{public_ip}:{PORT} (if firewall allows)")
    print(f"[service] 🔧 Workers: {MAX_WORKERS} concurrent Chrome instances")
    print(f"[service] 💡 Set MAX_WORKERS env var to change")
    print("=" * 60)
    print("[service] 📋 Endpoints:")
    print(f"[service]   POST /solve   - Solve Turnstile")
    print(f"[service]   GET  /health  - Check status")
    print(f"[service]   GET  /        - Service info")
    print("=" * 60)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[service] shutting down")
        server.server_close()
        if xvfb_proc:
            xvfb_proc.terminate()
