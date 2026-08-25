import os
from typing import Optional


LINE_BREAK_MARKER = "↵"


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

    # Keep collapsed line breaks distinguishable from ordinary whitespace.
    text = LINE_BREAK_MARKER.join(
        " ".join(line.split()) for line in text.splitlines()
    )

    if len(text) > max_chars or (max_lines and n_lines > max_lines):
        suffix = f" ({n_lines})" if include_line_count else ""
        return f"{text[:max_chars]}..{suffix}"
    else:
        return text


def truncate_output(
    text: str,
    max_bytes: int = 51200,  # 50 KB
) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text

    marker = (
        "\n... output truncated "
        f"(original: {len(encoded)} bytes); "
        "showing beginning and end ...\n"
    )

    # Preserve both ends so final errors and summaries are not discarded.
    marker_bytes = marker.encode("utf-8")
    available = max(0, max_bytes - len(marker_bytes))
    head_bytes = (available + 1) // 2
    tail_bytes = available // 2
    head = encoded[:head_bytes].decode("utf-8", errors="ignore")
    tail = (
        encoded[-tail_bytes:].decode("utf-8", errors="ignore")
        if tail_bytes
        else ""
    )
    return head + marker + tail


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
