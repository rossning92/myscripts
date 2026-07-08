#!/usr/bin/env python3
"""
Web-based remote file viewer.

Run on devserver:
    python3 server.py [--port 8765]

Auto-reloads when any .py or .html file in this directory is modified.
Connect from local browser via port forward, then open files with:
    ./ropen.sh /path/to/image.png
    ./ropen.sh https://example.com
"""

import http.server
import json
import mimetypes
import os
import queue
import signal
import subprocess
import sys
import threading
import time
import urllib.parse

DEFAULT_PORT = 8765
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
HISTORY_FILE = os.path.join(
    os.path.expanduser("~/.cache"), "ropen_history.json"
)
MAX_HISTORY = 100

item_id_counter = 0
opened_items = []
sse_clients = []
lock = threading.Lock()


def load_history():
    global item_id_counter, opened_items
    try:
        with open(HISTORY_FILE) as f:
            opened_items = json.load(f)[-MAX_HISTORY:]
    except (OSError, ValueError):
        opened_items = []
    item_id_counter = max((it["id"] for it in opened_items), default=0)


def save_history():
    try:
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        tmp = HISTORY_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(opened_items[-MAX_HISTORY:], f)
        os.replace(tmp, HISTORY_FILE)
    except OSError:
        pass


def next_id():
    global item_id_counter
    item_id_counter += 1
    return item_id_counter


def broadcast(item):
    msg = json.dumps(item)
    with lock:
        sse_clients[:] = [q for q in sse_clients if _try_put(q, msg)]


def _try_put(q, msg):
    try:
        q.put_nowait(msg)
        return True
    except Exception:
        return False


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path

        if path == "/":
            return self._serve_static("index.html")

        if path == "/api/events":
            return self._handle_sse()

        if path.startswith("/api/file/"):
            return self._serve_file(urllib.parse.unquote(path[9:]))

        if path.startswith("/api/stat/"):
            return self._serve_stat(urllib.parse.unquote(path[9:]))

        # Static files (view.html, etc.)
        if path.startswith("/"):
            return self._serve_static(path.lstrip("/"))

        self._json_err(404, "not found")

    def do_POST(self):
        if self.path == "/api/open":
            return self._handle_open()
        self._json_err(404, "not found")

    # --- Route handlers ---

    def _handle_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        q = queue.Queue()
        with lock:
            sse_clients.append(q)
        try:
            for item in opened_items:
                self.wfile.write(f"data: {json.dumps(item)}\n\n".encode())
            self.wfile.flush()
            while True:
                try:
                    self.wfile.write(f"data: {q.get(timeout=15)}\n\n".encode())
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with lock:
                if q in sse_clients:
                    sse_clients.remove(q)

    def _handle_open(self):
        length = int(self.headers.get("Content-Length", 0))
        params = urllib.parse.parse_qs(self.rfile.read(length).decode())
        fpath = params.get("path", [""])[0]
        if not fpath:
            return self._json_err(400, "missing path param")

        if not fpath.startswith(("http://", "https://")) and not os.path.isabs(fpath):
            cwd = params.get("cwd", [""])[0]
            if cwd:
                fpath = os.path.join(cwd, fpath)
            fpath = os.path.abspath(fpath)

        is_url = fpath.startswith(("http://", "https://"))
        item = {
            "id": next_id(),
            "path": fpath,
            "name": fpath if is_url else fpath.split("/")[-1].split("?")[0],
            "type": "url" if is_url else "file",
            "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        with lock:
            opened_items.append(item)
            del opened_items[:-MAX_HISTORY]
            save_history()
        broadcast(item)
        self._json_ok({"ok": True, "id": item["id"]})
        print(f"  opened: {fpath}")

    # --- Helpers ---

    def _serve_static(self, relpath):
        fpath = os.path.join(STATIC_DIR, relpath)
        if not os.path.isfile(fpath):
            return self._json_err(404, "not found")
        mime = mimetypes.guess_type(fpath)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(os.path.getsize(fpath)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        with open(fpath, "rb") as f:
            self.wfile.write(f.read())

    def _serve_stat(self, fpath):
        if not os.path.isfile(fpath):
            return self._json_err(404, "not found")
        st = os.stat(fpath)
        self._json_ok({"mtime": st.st_mtime, "size": st.st_size})

    def _serve_file(self, fpath):
        if not os.path.isfile(fpath):
            return self._json_err(404, "not found")
        mime = mimetypes.guess_type(fpath)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(os.path.getsize(fpath)))
        self.end_headers()
        with open(fpath, "rb") as f:
            while chunk := f.read(65536):
                self.wfile.write(chunk)

    def _json_ok(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json_err(self, code, msg):
        body = json.dumps({"error": msg}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def start_server(port):
    load_history()
    server = http.server.ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"serving on http://localhost:{port}")
    print(f"open files: ./ropen.sh <file_or_url>")
    server.serve_forever()


def _watched_mtimes(directory):
    mtimes = {}
    for name in os.listdir(directory):
        if name.endswith((".py", ".html")):
            mtimes[name] = os.path.getmtime(os.path.join(directory, name))
    static = os.path.join(directory, "static")
    if os.path.isdir(static):
        for name in os.listdir(static):
            if name.endswith((".html", ".js", ".css")):
                mtimes[f"static/{name}"] = os.path.getmtime(
                    os.path.join(static, name)
                )
    return mtimes


def run_with_reloader(port):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    last_mtimes = _watched_mtimes(base_dir)
    proc = None

    def cleanup(sig=None, frame=None):
        if proc and proc.poll() is None:
            proc.terminate()
            proc.wait()
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    while True:
        if proc is None or proc.poll() is not None:
            proc = subprocess.Popen(
                [sys.executable, __file__, "--serve", "--port", str(port)]
            )
            print(f"server started (pid {proc.pid})")

        time.sleep(1)
        try:
            current = _watched_mtimes(base_dir)
        except OSError:
            continue
        if current != last_mtimes:
            changed = set(current) ^ set(last_mtimes) | {
                k for k in current if current.get(k) != last_mtimes.get(k)
            }
            print(f"files changed: {', '.join(changed)}, restarting ...")
            last_mtimes = current
            proc.terminate()
            proc.wait()
            proc = None


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--serve", action="store_true", help=argparse.SUPPRESS)
    args = p.parse_args()

    if args.serve:
        start_server(args.port)
    else:
        run_with_reloader(args.port)
