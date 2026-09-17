import os
from typing import Any, Dict

from utils.encode_image_base64 import encode_image_base64

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


def get_tool_use_preview(args: Dict[str, Any]) -> str:
    file = args.get("file")
    return file if isinstance(file, str) else str(args)


def is_image_file(file: str) -> bool:
    return os.path.splitext(file)[1].lower() in _IMAGE_EXTENSIONS


def view_image(file: str) -> str:
    """View an image file (PNG, JPG, GIF, WebP, or BMP)."""

    if not is_image_file(file):
        return f"ERROR: unsupported image file: {file}"
    return encode_image_base64(file)
