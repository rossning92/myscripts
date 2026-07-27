import os
import subprocess
import sys

from utils.android import backup_pkg
from utils.menu import Menu
from utils.shutil import shell_open


def select_app_pkg():
    s = subprocess.check_output(
        ["adb", "shell", "pm list packages"], universal_newlines=True
    )
    s = s.replace("package:", "")
    lines = s.splitlines()
    lines = sorted(lines)
    i = Menu(items=lines, history="select_app_pkg").exec()
    if i == -1:
        return None
    else:
        return lines[i]


if __name__ == "__main__":
    pkg = os.environ.get("PKG_NAME")
    if not pkg:
        pkg = select_app_pkg()
        if not pkg:
            sys.exit(0)

    out_dir = os.environ.get("ANDROID_APP_BACKUP_DIR")
    if not out_dir:
        out_dir = os.path.expanduser("~/android_backup")

    os.makedirs(out_dir, exist_ok=True)

    backup_pkg(pkg, out_dir=out_dir)

    shell_open(out_dir)
