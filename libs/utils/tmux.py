from collections import defaultdict
import os
import shlex
import shutil
import subprocess
import sys
from typing import Iterable, Sequence


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


def _script_command(script: object) -> str:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    start_script = os.path.join(root, "bin", "start_script.py")
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
    return f"{select_command} 2>/dev/null || {start_command}"


def _script_menu_name(script: object) -> str:
    return os.path.basename(script.name)


def _bind_tmux_hotkey(key: str, scripts: Sequence[object]) -> None:
    if len(scripts) == 1:
        subprocess.check_call(
            ["tmux", "bind-key", key, "run-shell", _script_command(scripts[0])]
        )
        return

    menu_args = ["tmux", "bind-key", key, "display-menu", "-T", "Select script"]
    menu_scripts = sorted(
        ((_script_menu_name(script), script) for script in scripts),
        key=lambda item: (item[0].casefold(), item[0], item[1].script_path),
    )
    for index, (menu_name, script) in enumerate(menu_scripts, start=1):
        menu_hotkey = str(index) if index < 10 else "0" if index == 10 else ""
        menu_args.extend(
            [
                menu_name,
                menu_hotkey,
                f"run-shell {shlex.quote(_script_command(script))}",
            ]
        )
    subprocess.check_call(menu_args)


def register_tmux_hotkeys(scripts: Iterable[object]) -> None:
    """Replace runtime tmux bindings owned by myscripts."""
    if not is_in_tmux() or not is_tmux_installed():
        return

    scripts_by_key = defaultdict(list)
    for script in scripts:
        key = script.cfg["tmuxHotkey"]
        if not key or not script.is_supported():
            continue
        if any(char.isspace() for char in key):
            raise ValueError(f"tmuxHotkey must be a single tmux key: {key!r}")
        scripts_by_key[key].append(script)

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

    for key, matching_scripts in scripts_by_key.items():
        _bind_tmux_hotkey(key, matching_scripts)

    subprocess.check_call(
        [
            "tmux",
            "set-option",
            "-g",
            MYSCRIPTS_HOTKEY_OPTION,
            " ".join(scripts_by_key),
        ]
    )
