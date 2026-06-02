import os
import subprocess
import time

from utils.menu.confirmmenu import confirm
from utils.menu.diffmenu import DiffMenu
from utils.menu.menu import Menu


def _hg(*args):
    try:
        return subprocess.check_output(
            ["hg", *args], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except subprocess.CalledProcessError:
        return ""


def get_hg_status_items():
    status = _hg("status")
    if status:
        return status.splitlines(), False

    files = _hg("log", "-r", ".", "--template", "{files % '{file}\\n'}")
    items = [f"   {f}" for f in files.splitlines() if f.strip()]
    return items, True


def get_hg_prompt(is_clean: bool) -> str:
    repo_name = os.path.basename(os.getcwd())
    bookmark = _hg("log", "-r", ".", "--template", "{activebookmark}")
    if not bookmark:
        bookmark = _hg("log", "-r", ".", "--template", "{branch}") or "?"
    dirty = "" if is_clean else " *"
    return f"{repo_name} ({bookmark}{dirty})"


_HOTKEY_HINTS = "--- [^a]diff all [^d]discard [^r]refresh ---"


class HgMenu(Menu):
    def __init__(self, prompt_prefix: str = ""):
        super().__init__(close_on_selection=False)
        self._prompt_prefix = prompt_prefix
        self.set_header(_HOTKEY_HINTS)
        self.add_command(self._refresh, hotkey="ctrl+r")
        self.add_command(self._diff_all, hotkey="ctrl+a")
        self.add_command(self._discard, hotkey="ctrl+d")
        self._refresh()

    def get_item_color(self, item: str) -> str:
        status = item[:2]
        if "R" in status:
            return "red"
        if "?" in status:
            return "cyan"
        if "A" in status:
            return "green"
        if "M" in status:
            return "yellow"
        return "white"

    def _refresh(self):
        self._last_refresh_time = time.monotonic()
        items, is_clean = get_hg_status_items()
        self.is_clean = is_clean
        prompt = get_hg_prompt(is_clean)
        if self._prompt_prefix:
            prompt = f"{self._prompt_prefix} > {prompt}"
        self.set_prompt(prompt)
        self.items[:] = items
        self.set_message("refreshed")

    def _get_filename(self, item: str) -> str:
        return item[2:].strip()

    def _build_diff_cmd(self, *extra_args: str) -> list:
        cmd = ["hg", "diff", "-U10", "--color=always"]
        cmd.extend(extra_args)
        return cmd

    def _discard(self):
        items = list(self.get_selected_items())
        if not items:
            return
        names = [self._get_filename(item) for item in items]
        if not confirm(f"Discard changes to {len(names)} file(s)?", prompt_color="red"):
            return
        for item, filename in zip(items, names):
            status = item[:2].strip()
            if status == "?":
                path = os.path.join(os.getcwd(), filename)
                if os.path.isdir(path):
                    import shutil

                    shutil.rmtree(path)
                else:
                    os.remove(path)
            else:
                subprocess.run(["hg", "revert", "--no-backup", "--", filename])
        self._refresh()

    def on_idle(self):
        if time.monotonic() - self._last_refresh_time >= 10:
            self._refresh()

    def _diff_all(self):
        if self.is_clean:
            diff_cmd = self._build_diff_cmd("-c", ".")
        else:
            diff_cmd = self._build_diff_cmd()
        DiffMenu(root=os.getcwd(), diff_cmd=diff_cmd).exec()

    def on_item_selected(self, item):
        filename = self._get_filename(item)
        if self.is_clean:
            diff_cmd = self._build_diff_cmd("-c", ".", "--", filename)
        elif item.startswith("?"):
            diff_cmd = [
                "git",
                "diff",
                "--no-index",
                "-U10",
                "--color",
                os.devnull,
                filename,
            ]
        else:
            diff_cmd = self._build_diff_cmd("--", filename)
        DiffMenu(root=os.getcwd(), diff_cmd=diff_cmd).exec()


if __name__ == "__main__":
    repo_path = os.environ.get("HG_REPO", "")
    if repo_path:
        os.chdir(repo_path)

    HgMenu().exec()
