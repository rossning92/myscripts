"""Open a URL or local file in browsercli."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import mimetypes
from pathlib import Path
import subprocess
from threading import Thread
from urllib.parse import quote, urlsplit
from urllib.request import url2pathname


def open_image(path, content_type):
    image = path.read_bytes()
    route = "/" + quote(path.name, safe="")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != route:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(image)))
            self.end_headers()
            self.wfile.write(image)

        def log_message(self, *_args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05})
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}{route}"
            subprocess.run(["browsercli", "open", url], check=True)
        finally:
            server.shutdown()
            thread.join()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target")
    target = parser.parse_args().target
    path = Path(target)
    if target.lower().startswith("file://"):
        url = urlsplit(target)
        if url.netloc in ("", "localhost"):
            path = Path(url2pathname(url.path))

    if path.is_absolute() or path.is_file():
        path = path.absolute()
        if not path.is_file():
            parser.error(f"File not found: {path}")
        content_type, _ = mimetypes.guess_type(path)
        if content_type in ("image/png", "image/jpeg", "image/webp", "image/gif"):
            open_image(path, content_type)
            return
        target = path.as_uri()
    subprocess.run(["browsercli", "open", target], check=True)


if __name__ == "__main__":
    main()
