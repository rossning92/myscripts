import argparse
import getpass
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from _pkgmanager import require_package
from utils.process import start_process


def _server_address():
    if sys.platform == "win32":
        return rf"\\.\pipe\nvim-{getpass.getuser()}"
    return os.path.join(tempfile.gettempdir(), f"nvim-{getpass.getuser()}.sock")


def _remote(server, *args, check=False):
    return subprocess.run(
        ["nvim", "--headless", "--server", server, *args],
        capture_output=True,
        text=True,
        check=check,
    )


def _server_is_running(server):
    try:
        return _remote(server, "--remote-expr", "1").returncode == 0
    except OSError:
        return False


def _ensure_server(server):
    if _server_is_running(server):
        return

    if sys.platform != "win32" and os.path.exists(server):
        os.unlink(server)  # stale socket left by a crashed server

    start_process(["nvim", "--headless", "--listen", server])
    for _ in range(100):
        if _server_is_running(server):
            return
        time.sleep(0.05)
    raise RuntimeError(f"Neovim server did not start at {server}")


def open_in_neovim(path, line=None):
    require_package("neovim")
    server = _server_address()
    _ensure_server(server)

    _remote(server, "--remote", str(Path(path).expanduser().resolve()), check=True)
    if line is not None:
        # Neovim's --remote does not implement Vim's documented +{cmd} argument.
        _remote(server, "--remote-expr", f"cursor({line}, 1)", check=True)

    ui_count = _remote(
        server, "--remote-expr", "len(nvim_list_uis())", check=True
    ).stdout
    if ui_count == "0":
        # Not os.execvp(): Windows has no exec(), so the CRT emulation spawns the
        # UI asynchronously and exits, tearing the terminal down around it.
        sys.exit(subprocess.call(["nvim", "--server", server, "--remote-ui"]))


def _main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--line", "-l", type=int)
    args = parser.parse_args()
    open_in_neovim(args.path, args.line)


if __name__ == "__main__":
    _main()
