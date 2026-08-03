import argparse
import json
import mimetypes
import os
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageOps
from utils.browser import open_url


HTML_FILE = Path(__file__).with_name("crop_images_interactive.html")


def _select_roi_in_browser(image_file: str) -> Optional[Tuple[int, int, int, int]]:
    token = secrets.token_urlsafe(18)
    result = {}
    finished = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in (f"/{token}", f"/{token}/"):
                self._send(
                    200,
                    "text/html; charset=utf-8",
                    HTML_FILE.read_bytes(),
                )
            elif self.path == f"/{token}/image":
                with open(image_file, "rb") as f:
                    self._send(
                        200,
                        mimetypes.guess_type(image_file)[0] or "application/octet-stream",
                        f.read(),
                    )
            elif self.path == "/favicon.ico":
                self._send(204, "image/x-icon", b"")
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path != f"/{token}/crop":
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                data = json.loads(self.rfile.read(length))
                with Image.open(image_file) as im:
                    width, height = ImageOps.exif_transpose(im).size
                x = max(0, min(width, round(float(data["x"]))))
                y = max(0, min(height, round(float(data["y"]))))
                right = max(x + 1, min(width, round(float(data["x"] + data["w"]))))
                bottom = max(y + 1, min(height, round(float(data["y"] + data["h"]))))
                result["rect"] = (x, y, right - x, bottom - y)
                self._send(200, "application/json", b'{"ok":true}')
                finished.set()
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                self.send_error(400, str(error))

        def _send(self, status, content_type, content):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, _format, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/{token}/"
    print(f"Crop editor: {url}")
    try:
        open_url(url)
        finished.wait()
        return result.get("rect")
    except KeyboardInterrupt:
        return None
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def crop_images_interactive(files: List[str]):
    rect = _select_roi_in_browser(files[0])
    if rect is None:
        return

    for file in files:
        out_dir = os.path.join(os.path.dirname(file), "out")
        os.makedirs(out_dir, exist_ok=True)
        out_file = os.path.join(out_dir, os.path.basename(file))
        with Image.open(file) as source:
            source_format = source.format
            image = ImageOps.exif_transpose(source)
            image = image.crop((rect[0], rect[1], rect[0] + rect[2], rect[1] + rect[3]))
            save_args = {"quality": 90} if source_format in ("JPEG", "WEBP") else {}
            image.save(out_file, **save_args)
        print(f"Saved: {out_file}")


def _main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+", help="input image files")
    args = parser.parse_args()
    crop_images_interactive(args.files)


if __name__ == "__main__":
    _main()
