import os
import subprocess

from utils.menu.confirmmenu import confirm
from utils.menu.diffmenu import DiffMenu
from utils.menu.menu import Menu


def get_git_status_items():
    try:
        status = subprocess.check_output(
            ["git", "status", "--short"], universal_newlines=True
        )
        if status.strip():
            return status.splitlines(), False
        else:
            # Clean working tree, show changes in HEAD
            show_output = subprocess.check_output(
                ["git", "show", "--name-status", "--format=", "HEAD"],
                universal_newlines=True,
            )
            items = []
            for line in show_output.splitlines():
                if line.strip():
                    # git show --name-status gives "M\tfile"
                    # convert to "M  file" to match "git status -s" format (XY file)
                    parts = line.split("\t", 1)
                    if len(parts) == 2:
                        items.append(f"{parts[0]:<2} {parts[1]}")
                    else:
                        items.append(line)
            return items, True
    except subprocess.CalledProcessError:
        return [], False


def get_git_prompt(is_clean: bool) -> str:
    repo_name = os.path.basename(os.getcwd())
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except subprocess.CalledProcessError:
        branch = "?"
    dirty = "" if is_clean else " *"
    return f"{repo_name} ({branch}{dirty})>"


_HOTKEY_HINTS = "--- [^a]diff all [^s]stage [^u]unstage [^d]discard [^r]refresh ---"


class GitMenu(Menu):
    def __init__(self):
        super().__init__(close_on_selection=False)
        self.set_header(_HOTKEY_HINTS)
        self.add_command(self._refresh, hotkey="ctrl+r")
        self.add_command(self._diff_all, hotkey="ctrl+a")
        self.add_command(self._stage, hotkey="ctrl+s")
        self.add_command(self._unstage, hotkey="shift+u")
        self.add_command(self._discard, hotkey="ctrl+d")
        self._refresh()

    def get_item_color(self, item: str) -> str:
        status = item[:2]
        if "D" in status:
            return "red"
        if "?" in status:
            return "cyan"
        if "A" in status:
            return "green"
        if "M" in status or "R" in status:
            return "yellow"
        return "white"

    def _refresh(self):
        items, is_clean = get_git_status_items()
        self.is_clean = is_clean

        self.set_prompt(get_git_prompt(is_clean))

        self.items[:] = items
        self.refresh()

        self.set_message("refreshed")

    def _get_filename(self, item: str) -> str:
        name = item[3:]
        if " -> " in name:
            name = name.split(" -> ")[-1].strip('"')
        return name

    def _stage(self):
        for item in self.get_selected_items():
            filename = self._get_filename(item)
            subprocess.run(["git", "add", "--", filename])
        self._refresh()

    def _unstage(self):
        for item in self.get_selected_items():
            filename = self._get_filename(item)
            subprocess.run(["git", "reset", "HEAD", "--", filename])
        self._refresh()

    def _discard(self):
        items = list(self.get_selected_items())
        if not items:
            return
        names = [self._get_filename(item) for item in items]
        if not confirm(f"Discard changes to {len(names)} file(s)?"):
            return
        for item, filename in zip(items, names):
            status = item[:2]
            if "?" in status:
                # Untracked file: remove it
                path = os.path.join(os.getcwd(), filename)
                if os.path.isdir(path):
                    subprocess.run(["git", "clean", "-fd", "--", filename])
                else:
                    os.remove(path)
            else:
                # Tracked file: restore to HEAD
                subprocess.run(["git", "checkout", "HEAD", "--", filename])
        self._refresh()

    def _diff_all(self):
        if self.is_clean:
            git_args = ["HEAD~1", "HEAD"]
        else:
            git_args = []
        DiffMenu(git_args=git_args).exec()

    def on_item_selected(self, item):
        filename = self._get_filename(item)

        if self.is_clean:
            git_args = ["HEAD~1", "HEAD", filename]
        elif item.startswith("??"):
            git_args = ["--no-index", os.devnull, filename]
        else:
            git_args = [filename]

        DiffMenu(git_args=git_args).exec()


if __name__ == "__main__":
    repo_path = os.environ.get("GIT_REPO", "")
    if repo_path:
        os.chdir(repo_path)

    GitMenu().exec()
