"""Let the user choose which script owns a conflicting Linux global hotkey."""

import argparse
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "libs"))

from _script import Script, start_script
from _shutil import prepend_to_path
from utils.menu import Menu


def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scripts", nargs="+")
    args = parser.parse_args()

    scripts = [Script(path) for path in args.scripts]
    scripts.sort(
        key=lambda script: (
            os.path.basename(script.script_path).casefold(),
            os.path.basename(script.script_path),
            script.script_path,
        )
    )
    menu = Menu(
        items=[os.path.basename(script.script_path) for script in scripts],
        prompt="select script",
        allow_input=False,
        enable_command_palette=False,
        quick_select=True,
    )
    selected_index = menu.exec()
    if selected_index < 0:
        return
    selected = scripts[selected_index]

    prepend_to_path(os.path.dirname(sys.executable))
    start_script(file=selected.script_path, restart_instance=None)


if __name__ == "__main__":
    _main()
