import os
from typing import Optional


def truncate_text(
    text: str,
    max_chars: int = 240,
    max_lines: Optional[int] = None,
    include_line_count: bool = True,
) -> str:
    lines = text.splitlines()
    n_lines = len(lines)
    if max_lines is not None and n_lines > max_lines:
        text = "\n".join(lines[:max_lines])

    text = " ".join(text.split())

    if len(text) > max_chars or (max_lines and n_lines > max_lines):
        prefix = f"({n_lines}) " if include_line_count else ""
        return f"{prefix}{text[:max_chars]}.."
    else:
        return text


def truncate_output(
    text: str,
    max_lines: int = 2000,
    max_bytes: int = 51200,  # 50 KB
) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines and len(text.encode("utf-8")) <= max_bytes:
        return text

    # Truncate to max_lines
    truncated_lines = lines[:max_lines]
    preview = "\n".join(truncated_lines)

    # Further truncate if still exceeds max_bytes
    preview_bytes = preview.encode("utf-8")
    if len(preview_bytes) > max_bytes:
        preview = (
            preview_bytes[:max_bytes].decode("utf-8", errors="ignore")
            + "\n... [preview truncated]"
        )

    num_truncated = len(lines) - len(preview.splitlines())

    return f"{preview}\n... {num_truncated} lines truncated ..."


def is_text_file(filepath: str, encoding="utf-8", buffer_size=4096, threshold=0.9):
    if not os.path.exists(filepath):
        return False

    if os.path.isdir(filepath):
        return False

    try:
        with open(filepath, "rb") as f:
            buffer = f.read(buffer_size)
        if not buffer:
            return True
        decoded = buffer.decode(encoding, errors="replace")
        total_chars = len(decoded)
        if total_chars == 0:
            return True
        invalid_chars = decoded.count("\ufffd")
        valid_ratio = (total_chars - invalid_chars) / total_chars
        return valid_ratio >= threshold

    except Exception as e:
        print(f"An error occurred while checking file {filepath}: {e}")
        return False
