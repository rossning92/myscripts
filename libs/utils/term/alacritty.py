import os
import shutil
import sys
from pathlib import Path
from typing import Optional, Tuple

from _shutil import file_is_old


def is_alacritty_installed():
    return shutil.which("alacritty")


# https://github.com/alacritty/alacritty/blob/master/alacritty.toml
def setup_alacritty():
    if not is_alacritty_installed():
        raise FileNotFoundError("Alacritty is not installed")

    src_config = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "settings"
        / "alacritty"
        / "alacritty.toml"
    ).resolve()

    if sys.platform == "win32":
        dest_config = os.path.expandvars(r"%APPDATA%\alacritty\alacritty.toml")
    else:
        dest_config = os.path.expanduser("~/.config/alacritty/alacritty.toml")
    os.makedirs(os.path.dirname(dest_config), exist_ok=True)

    if file_is_old(src_config, dest_config):
        shutil.copy(src_config, dest_config)


def wrap_args_alacritty(
    args,
    borderless: bool = False,
    dynamic_title: bool = False,
    font_size: Optional[int] = None,
    font: Optional[str] = None,
    maximized: bool = False,
    padding: Optional[int] = None,
    position: Optional[Tuple[int, int]] = None,
    title: Optional[str] = None,
    **kwargs,
):
    assert isinstance(args, list)

    setup_alacritty()

    out_args = ["alacritty"]

    # Specify option key value pairs
    options = []
    if dynamic_title:
        options += ["window.dynamic_title=true"]
    if maximized:
        options += [
            'window.startup_mode="Maximized"',
            "window.dimensions.columns=0",
            "window.dimensions.lines=0",
        ]
    if font_size is None and sys.platform == "darwin":
        font_size = 14
    if font_size is not None:
        options += [
            f"font.size={font_size}",
        ]
    if font is not None:
        options += [f'font.normal.family="{font}"']
    if borderless:
        options += ['window.decorations="none"']
    if position:
        options += [
            f"window.position.x={position[0]}",
            f"window.position.y={position[1]}",
        ]
    if padding is not None:
        options += [f"window.padding.x={padding}", f"window.padding.y={padding}"]
    for opt in options:
        out_args += ["-o", opt]

    if title:
        out_args += ["--title", title]

    if sys.platform == "win32":
        # HACK: Alacritty handles spaces in a weird way: if the argument has
        # spaces in it, you must double quote it. Backslashes will need to be
        # replaced with 2 backslashes otherwise they will disappear for some
        # reason.
        args = ['"' + x.replace("\\", "\\\\") + '"' if " " in x else x for x in args]

    out_args += ["-e"] + args
    return out_args
