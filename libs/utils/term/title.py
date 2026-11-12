"""Terminal titles, written directly or through a restricted host relay."""

import ctypes
import os
from pathlib import Path
import socket
import sys
import threading


SOCKET_ENV = "TERMINAL_TITLE_SOCKET"


def clean_title(title):
    return " ".join("".join(char if char.isprintable() else " " for char in title).split())[:160]


def set_terminal_title(title, tty=None):
    title = clean_title(title)
    relay = os.environ.get(SOCKET_ENV)
    if relay:
        # A configured relay never falls back to accessing a terminal device.
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as client:
            client.settimeout(0.5)
            client.sendto(title.encode("utf-8"), relay)
    elif sys.platform == "win32":
        ctypes.windll.kernel32.SetConsoleTitleW(title)
    elif tty:
        with open(tty, "w", encoding="utf-8") as output:
            output.write(f"\033]0;{title}\007")
    else:
        sys.stdout.write(f"\033]0;{title}\007")
        sys.stdout.flush()


class TerminalTitleRelay:
    """Accept title text only; the host chooses and owns the terminal device."""

    def __init__(self, socket_path, tty):
        self.socket_path = Path(socket_path)
        self.tty = tty

    def __enter__(self):
        self.fd = os.open(self.tty, os.O_WRONLY | os.O_NOCTTY | os.O_NONBLOCK)
        try:
            self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            self.socket.bind(str(self.socket_path))
            self.socket.settimeout(0.5)
        except BaseException:
            os.close(self.fd)
            if hasattr(self, "socket"):
                self.socket.close()
            raise
        self.closed = threading.Event()
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()
        return self

    def serve(self):
        while not self.closed.is_set():
            try:
                data = self.socket.recv(4096)
                title = clean_title(data.decode("utf-8", errors="replace"))
                os.write(self.fd, f"\033]0;{title}\007".encode("utf-8"))
            except socket.timeout:
                continue
            except OSError:
                if self.closed.is_set():
                    break

    def __exit__(self, *exc):
        self.closed.set()
        self.thread.join()
        self.socket.close()
        os.close(self.fd)
        self.socket_path.unlink(missing_ok=True)
