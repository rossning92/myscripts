import os
import subprocess

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


class GitMenu(Menu):
    def __init__(self):
        super().__init__(close_on_selection=False)
        self.add_command(self._refresh, hotkey="ctrl+r")
        self.add_command(self._view_all, hotkey="ctrl+a")
        self._refresh()

    def _refresh(self):
        items, is_clean = get_git_status_items()
        self.is_clean = is_clean

        self.set_prompt(get_git_prompt(is_clean))

        self.clear_items()
        for item in items:
            self.append_item(item)

        self.set_message("refreshed")

    def _view_all(self):
        if self.is_clean:
            git_args = ["HEAD~1", "HEAD"]
        else:
            git_args = []
        DiffMenu(git_args=git_args).exec()

    def on_item_selected(self, item):
        filename = item[3:]
        if " -> " in filename:
            filename = filename.split(" -> ")[-1].strip('"')

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
