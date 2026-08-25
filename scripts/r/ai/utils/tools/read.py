import os
from itertools import islice
from typing import Any, Dict

from utils.encode_image_base64 import encode_image_base64

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


def get_tool_use_preview(args: Dict[str, Any]) -> str:
    file = args.get("file")
    if not isinstance(file, str):
        return str(args)

    options = [
        f"{name}={args[name]}" for name in ("offset", "limit") if name in args
    ]
    return f"{file} ({', '.join(options)})" if options else file


def _is_image_file(file: str) -> bool:
    return os.path.splitext(file)[1].lower() in _IMAGE_EXTENSIONS


def read(file: str, offset: int = 0, limit: int = 2000) -> str:
    """
    Read up to `limit` lines from `file`, starting at `offset` (0-based). This tool can also read image files (PNG, JPG, etc.) - the image content will be visible to you directly.

    - You should always use `read` tool instead of `cat` command.
    """

    if _is_image_file(file):
        return encode_image_base64(file)

    if limit <= 0:
        return f"ERROR: limit must be > 0 (got {limit})"

    with open(file, "r", encoding="utf-8", errors="ignore") as f:
        for _ in range(offset):
            if not f.readline():
                return f"ERROR: offset {offset} is beyond end of file"

        lines = list(islice(f, limit))
        next_line = f.readline()

        if not next_line:
            return "".join(lines)

        remaining = 1 + sum(1 for _ in f)
        total = offset + len(lines) + remaining
        result = "".join(lines)
        return result + f"\n... ({remaining} remaining lines, total {total})"
