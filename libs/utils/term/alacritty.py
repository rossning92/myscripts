import os
import shutil
import sys
from pathlib import Path
from typing import Optional, Tuple

def is_alacritty_installed():
    return shutil.which("alacritty")


# https://github.com/alacritty/alacritty/blob/master/alacritty.toml
def _get_settings_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent / "settings" / "alacritty"


def _force_symlink(src: Path, dest: Path):
    """Point dest at src, replacing any existing file or symlink."""
    if dest.is_symlink() and dest.resolve() == src.resolve():
        return
    if dest.is_symlink() or dest.exists():
        dest.unlink()
    os.symlink(src, dest)


def setup_alacritty():
    if not is_alacritty_installed():
        raise FileNotFoundError("Alacritty is not installed")

    settings_dir = _get_settings_dir()
    config_dir = _get_alacritty_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)

    _force_symlink(settings_dir / "alacritty.toml", config_dir / "alacritty.toml")

    current_theme = config_dir / "current-theme.toml"
    if not current_theme.is_symlink() and not current_theme.exists():
        os.symlink(_get_themes_dir() / "dracula.toml", current_theme)

    # macOS-only font size: symlink font-mac.toml so the
    # "~/.config/alacritty/font-mac.toml" import in alacritty.toml resolves.
    # On other platforms remove it so the import is skipped.
    dest_font = config_dir / "font-mac.toml"
    if sys.platform == "darwin":
        _force_symlink(settings_dir / "font-mac.toml", dest_font)
    elif dest_font.is_symlink() or dest_font.exists():
        dest_font.unlink()


def _get_alacritty_config_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.path.expandvars(r"%APPDATA%\alacritty"))
    else:
        return Path(os.path.expanduser("~/.config/alacritty"))


def _get_themes_dir() -> Path:
    return _get_settings_dir() / "themes"


def toggle_alacritty_theme():
    themes_dir = _get_themes_dir()
    current = _get_alacritty_config_dir() / "current-theme.toml"
    dark = themes_dir / "dracula.toml"
    light = themes_dir / "alucard.toml"

    if current.is_symlink() and current.resolve() == dark.resolve():
        target = light
    else:
        target = dark

    current.unlink(missing_ok=True)
    os.symlink(target, current)
    return target.stem


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
    # On macOS the default size comes from font.toml (imported by alacritty.toml).
    # Only override here when a caller passes an explicit font_size.
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
