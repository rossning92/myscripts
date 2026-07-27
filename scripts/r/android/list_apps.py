import os
import subprocess
import sys

from _script import set_variable, start_script
from _shutil import call_echo
from utils.android import backup_pkg, get_apk_path
from utils.clip import set_clip
from utils.menu import Menu
from utils.menu.actionmenu import ActionMenu
from utils.shutil import shell_open

SCRIPT_NAME = os.path.splitext(os.path.basename(__file__))[0]


def select_app_pkg():
    s = subprocess.check_output(
        ["adb", "shell", "pm list packages"], universal_newlines=True
    )
    s = s.replace("package:", "")
    lines = s.splitlines()
    lines = sorted(lines)
    i = Menu(items=lines, history=SCRIPT_NAME).exec()
    if i == -1:
        return None
    else:
        return lines[i]


class AppActionMenu(ActionMenu):
    def __init__(self, pkg: str, **kwargs):
        self.pkg = pkg
        super().__init__(**kwargs)

    @ActionMenu.action()
    def restart_app(self):
        start_script("r/android/restart_app.py")

    @ActionMenu.action()
    def restart_app_with_logcat(self):
        start_script("r/android/restart_app_logcat.sh")

    @ActionMenu.action()
    def set_variable_package_name(self):
        set_variable("PKG_NAME", self.pkg)

    @ActionMenu.action()
    def copy_package_name_to_clipboard(self):
        set_clip(self.pkg)

    @ActionMenu.action()
    def backup_app(self):
        out_dir = os.environ.get("ANDROID_APP_BACKUP_DIR")
        if not out_dir:
            out_dir = os.path.expanduser("~/android_backup")
        os.makedirs(out_dir, exist_ok=True)
        backup_pkg(self.pkg, out_dir=out_dir)
        shell_open(out_dir)

    @ActionMenu.action(name="get_apk_path")
    def _get_apk_path(self):
        print(get_apk_path(self.pkg))
        input("(press enter key to exit...)")

    @ActionMenu.action()
    def uninstall_app(self):
        call_echo(["adb", "uninstall", self.pkg])

    @ActionMenu.action()
    def dumpsys_package(self):
        lines = subprocess.check_output(
            ["adb", "shell", f"dumpsys package {self.pkg}"], universal_newlines=True
        ).splitlines()
        Menu(items=lines).exec()

    @ActionMenu.action()
    def dumpsys_package_permission(self):
        lines = subprocess.check_output(
            ["adb", "shell", f"dumpsys package {self.pkg} | grep permission"],
            universal_newlines=True,
        ).splitlines()
        Menu(items=lines).exec()

    @ActionMenu.action()
    def get_app_version(self):
        call_echo(["run_script", "r/android/get_app_version.sh"])
        input("(press enter to continue)")


if __name__ == "__main__":
    pkg = select_app_pkg()
    if not pkg:
        sys.exit(0)
    else:
        set_variable("PKG_NAME", pkg)

    AppActionMenu(pkg=pkg, close_on_selection=True).exec()
