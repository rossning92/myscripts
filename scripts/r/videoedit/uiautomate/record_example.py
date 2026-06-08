import os

from utils.logger import setup_logger
from utils.shutil import shell_open

from .record_screen import record_app


def record_explorer(file):
    record_app(
        title="bin",
        args=["explorer", r"C:\tools\ffmpeg-master-latest-win64-gpl-shared\bin"],
        file=file,
    )


def record_chrome(file):
    record_app(
        args=["chrome", "--new-window", "www.google.com"],
        file=file,
    )


if __name__ == "__main__":
    setup_logger()
    file = os.path.expanduser("~/Desktop/test.mp4")
    record_chrome(file)
    shell_open(file)
