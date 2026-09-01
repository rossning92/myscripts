import os
from pathlib import Path
from typing import Optional


def get_display_path(path: str) -> str:
    path_obj = Path(path)
    try:
        relative_path = path_obj.relative_to(Path.home())
    except ValueError:
        return str(path_obj)
    return str(Path("~") / relative_path)


def read_last_line(file: str) -> str:
    with open(file, "rb") as f:
        try:  # catch OSError in case of a one line file
            f.seek(-2, os.SEEK_END)
            while f.read(1) != b"\n":
                f.seek(-2, os.SEEK_CUR)
        except OSError:
            f.seek(0)
        last_line = f.readline().decode()
        return last_line


def read_last_non_empty_line(file: str) -> Optional[str]:
    with open(file, "r") as f:
        lines = f.read().splitlines()
    for line in reversed(lines):
        if line != "":
            return line
    return None


def human_readable_size(num):
    for unit in ("B", "k", "M", "G", "T", "P", "E", "Z"):
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}"
        num /= 1024.0
    return f"{num:.1f}Y"
