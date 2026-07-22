import os
import shlex
import shutil
import subprocess
import sys
from typing import Iterable


MYSCRIPTS_HOTKEY_OPTION = "@myscripts-tmux-hotkeys"


def is_in_tmux() -> bool:
    return bool(os.environ.get("TMUX"))


def is_tmux_installed() -> bool:
    return shutil.which("tmux") is not None


def has_tmux_session() -> bool:
    if not is_tmux_installed():
        return False

    result = subprocess.run(
        ["tmux", "ls"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def register_tmux_hotkeys(scripts: Iterable[object]) -> None:
    """Replace runtime tmux bindings owned by myscripts."""
    if not is_in_tmux() or not is_tmux_installed():
        return

    previous = subprocess.run(
        ["tmux", "show-option", "-gv", MYSCRIPTS_HOTKEY_OPTION],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if previous.returncode == 0:
        for key in previous.stdout.split():
            subprocess.run(
                ["tmux", "unbind-key", key],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    start_script = os.path.join(root, "bin", "start_script.py")
    registered = []
    for script in scripts:
        key = script.cfg["tmuxHotkey"]
        if not key or not script.is_supported():
            continue
        if any(char.isspace() for char in key):
            raise ValueError(f"tmuxHotkey must be a single tmux key: {key!r}")

        start_command = shlex.join(
            [
                sys.executable,
                start_script,
                "--restart-instance=auto",
                script.script_path,
            ]
        )
        select_command = shlex.join(
            ["tmux", "select-window", "-t", f"={script.get_window_title()}"]
        )
        command = f"{select_command} 2>/dev/null || {start_command}"
        subprocess.check_call(["tmux", "bind-key", key, "run-shell", command])
        registered.append(key)

    subprocess.check_call(
        ["tmux", "set-option", "-g", MYSCRIPTS_HOTKEY_OPTION, " ".join(registered)]
    )
