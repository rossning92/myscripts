#!/usr/bin/env python3
"""Open a file or URL in the ropen viewer, starting its daemon if needed."""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "libs"))
from utils.shutil import shell_open


DEFAULT_PORT = 8765
STARTUP_TIMEOUT = 5


def _send_request(port: int, target: str, cwd: str) -> bool:
    data = urllib.parse.urlencode({"path": target, "cwd": cwd}).encode()
    request = urllib.request.Request(
        f"http://localhost:{port}/api/open", data=data, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=1):
            return True
    except urllib.error.HTTPError as error:
        print(f"error: ropen server returned HTTP {error.code}", file=sys.stderr)
        raise SystemExit(1) from error
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return False


def _target_url(port: int, target: str, cwd: str) -> str:
    if target.startswith(("http://", "https://")):
        return target
    path = Path(target)
    if not path.is_absolute():
        path = Path(cwd) / path
    query = urllib.parse.urlencode({"path": str(path.resolve())})
    return f"http://localhost:{port}/view.html?{query}"


def _start_server(port: int) -> None:
    server_script = Path(__file__).resolve().with_name("server.py")
    subprocess.Popen(
        [sys.executable, str(server_script), "--serve", "--port", str(port)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def _main() -> int:
    parser = argparse.ArgumentParser(prog="ropen")
    parser.add_argument("target", help="file path or URL to open")
    args = parser.parse_args()

    try:
        port = int(os.environ.get("ROPEN_PORT", DEFAULT_PORT))
    except ValueError:
        parser.error("ROPEN_PORT must be an integer")

    cwd = os.getcwd()
    if not _send_request(port, args.target, cwd):
        _start_server(port)
        deadline = time.monotonic() + STARTUP_TIMEOUT
        while time.monotonic() < deadline:
            time.sleep(0.1)
            if _send_request(port, args.target, cwd):
                break
        else:
            print(
                f"error: could not start ropen server on port {port}",
                file=sys.stderr,
            )
            return 1

    shell_open(_target_url(port, args.target, cwd))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(_main())
    except KeyboardInterrupt:
        sys.exit(130)
