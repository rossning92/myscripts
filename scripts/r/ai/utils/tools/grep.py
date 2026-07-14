import argparse
import os
import re
import shutil
import subprocess
from typing import Iterator, List, Optional, Tuple

MAX_LINES = 1000
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "venv",
}


def _format_result(lines: List[str], truncated: bool) -> str:
    if not lines:
        return "No matches found"
    result = "\n".join(lines)
    if truncated:
        result += f"\n\n(Truncated to {MAX_LINES} lines; narrow your search.)"
    return result


def _grep_with_rg(pattern: str) -> Optional[str]:
    if shutil.which("rg") is None:
        return None

    process = subprocess.Popen(
        ["rg", "--heading", "--line-number", pattern],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    assert process.stdout is not None, "stdout should not be None"
    lines: List[str] = []
    truncated = False

    for line in process.stdout:
        lines.append(line.rstrip())

        if len(lines) >= MAX_LINES:
            truncated = True
            process.terminate()
            break

    process.wait()
    return _format_result(lines, truncated)


def _iter_files(root: str) -> Iterator[str]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            dirname
            for dirname in dirnames
            if dirname not in SKIP_DIRS and not dirname.startswith(".")
        ]

        for filename in filenames:
            if filename.startswith("."):
                continue
            yield os.path.join(dirpath, filename)


def _read_lines(path: str) -> Iterator[Tuple[int, str]]:
    with open(path, "rb") as f:
        chunk = f.read(8192)
        if b"\0" in chunk:
            return
        f.seek(0)
        for line_number, line in enumerate(f, start=1):
            yield line_number, line.decode("utf-8", errors="replace").rstrip("\r\n")


def _relative_path(path: str) -> str:
    relpath = os.path.relpath(path, os.getcwd())
    return relpath if relpath != "." else path


def _grep_with_python(pattern: str) -> str:
    try:
        regex = re.compile(pattern)
    except re.error as e:
        return f"regex parse error:\n    {e}"

    lines: List[str] = []
    truncated = False

    for path in _iter_files(os.getcwd()):
        file_lines: List[str] = []

        try:
            for line_number, line in _read_lines(path):
                if regex.search(line):
                    file_lines.append(f"{line_number}:{line}")
        except (OSError, UnicodeError):
            continue

        if not file_lines:
            continue

        if lines:
            lines.append("")
        lines.append(_relative_path(path))
        lines.extend(file_lines)

        if len(lines) >= MAX_LINES:
            lines = lines[:MAX_LINES]
            truncated = True
            break

    return _format_result(lines, truncated)


def grep(pattern: str) -> str:
    """
    Fast content search tool for any codebase size that finds files with specific patterns in their content.

    - Recursively searches file contents from the current directory.
    - Supports full regular expression pattern matching.
    - IMPORTANT: Always use `grep_tool` instead of command-line tools like `find` or `grep` for searches.

    :param pattern: The regular expression pattern to search for.
    """

    result = _grep_with_rg(pattern)
    if result is not None:
        return result
    return _grep_with_python(pattern)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pattern", help="The regular expression pattern to search for.")
    args = parser.parse_args()

    result = grep(args.pattern)
    print(result)
