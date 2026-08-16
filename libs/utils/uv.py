import re
from pathlib import Path
from typing import Dict, List, Optional

from _pkgmanager import require_package


def find_uv_project(script_path: str) -> Optional[str]:
    """Return the nearest parent directory that declares a uv project."""
    directory = Path(script_path).resolve().parent
    for parent in (directory, *directory.parents):
        pyproject = parent / "pyproject.toml"
        if (parent / "uv.lock").is_file():
            return str(parent)
        if pyproject.is_file():
            try:
                content = pyproject.read_text(encoding="utf-8")
            except OSError:
                content = ""
            if re.search(r"^\s*\[tool\.uv(?:\.[^]]+)?\]\s*(?:#.*)?$", content, re.M):
                return str(parent)
    return None


def ensure_uv_available(
    *,
    wsl: bool = False,
    env: Optional[Dict[str, str]] = None,
    proot_distro: Optional[str] = None,
) -> bool:
    """Install uv through the configured platform package manager if needed."""
    return require_package("uv", wsl=wsl, env=env, proot_distro=proot_distro)


def get_uv_python_executable(
    uv_project: Optional[str], default_python: str
) -> str:
    """Use the Python selected by uv when a project was detected."""
    return "python" if uv_project else default_python


def wrap_uv_command(command: List[str], uv_project: str) -> List[str]:
    """Run a command in uv's managed project environment."""
    return ["uv", "run", "--project", uv_project, *command]
