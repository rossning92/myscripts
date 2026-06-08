import os
import subprocess

from utils.menu.diffmenu import DiffMenu
from utils.menu.shellcmdmenu import ShellCmdMenu

from git.vcs_menu import VcsDiffMenu


class GitMenu(VcsDiffMenu):
    _HOTKEY_HINTS = "--- [^a]diff all [^s]stage [^u]unstage [^d]discard [!c]commit [^r]refresh ---"

    def _init_extra_commands(self):
        self.add_command(self.__stage, hotkey="ctrl+s")
        self.add_command(self.__unstage, hotkey="shift+u")

    def _get_status_items(self):
        try:
            status = subprocess.check_output(
                ["git", "status", "--short", "-u"], universal_newlines=True
            )
            if status.strip():
                return status.splitlines(), False
            else:
                show_output = subprocess.check_output(
                    ["git", "show", "--name-status", "--format=", "HEAD"],
                    universal_newlines=True,
                )
                items = []
                for line in show_output.splitlines():
                    if line.strip():
                        parts = line.split("\t", 1)
                        if len(parts) == 2:
                            items.append(f"{parts[0]:<2} {parts[1]}")
                        else:
                            items.append(line)
                return items, True
        except subprocess.CalledProcessError:
            return [], False

    def _get_vcs_prompt(self, is_clean):
        repo_name = self._repo_display_name()
        try:
            branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except subprocess.CalledProcessError:
            branch = "?"
        if is_clean:
            try:
                commit_info = subprocess.check_output(
                    ["git", "log", "-1", "--format=%h %s"],
                    text=True,
                    stderr=subprocess.DEVNULL,
                ).strip()
            except subprocess.CalledProcessError:
                commit_info = ""
            if commit_info:
                return f"{repo_name} ({branch}) {commit_info}"
            return f"{repo_name} ({branch})"
        return f"{repo_name} ({branch} *)"

    def get_item_color(self, item):
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

    def _get_filename(self, item):
        name = item[3:]
        if " -> " in name:
            name = name.split(" -> ")[-1].strip('"')
        return name

    def _discard_file(self, item, filename):
        status = item[:2]
        if "?" in status:
            path = os.path.join(os.getcwd(), filename)
            if os.path.isdir(path):
                subprocess.run(["git", "clean", "-fd", "--", filename])
            else:
                os.remove(path)
        else:
            subprocess.run(["git", "checkout", "HEAD", "--", filename])

    def __stage(self):
        for item in self.get_selected_items():
            filename = self._get_filename(item)
            subprocess.run(["git", "add", "--", filename])
        self._refresh()

    def __unstage(self):
        for item in self.get_selected_items():
            filename = self._get_filename(item)
            subprocess.run(["git", "reset", "HEAD", "--", filename])
        self._refresh()

    def _commit_files(self, filenames, message):
        cmds = [["git", "add", "--"] + filenames, ["git", "commit", "-m", message]]
        shell_cmd = " && ".join(subprocess.list2cmdline(cmd) for cmd in cmds)
        ShellCmdMenu(shell_cmd).exec()

    def _diff_all(self):
        if self._is_clean:
            git_args = ["HEAD~1", "HEAD"]
        else:
            git_args = []
        DiffMenu(git_args=git_args, prompt_prefix=self.get_prompt()).exec()

    def on_item_selected(self, item):
        filename = self._get_filename(item)
        if self._is_clean:
            git_args = ["HEAD~1", "HEAD", filename]
        elif item.startswith("??"):
            git_args = ["--no-index", os.devnull, filename]
        else:
            git_args = [filename]
        DiffMenu(git_args=git_args, prompt_prefix=self.get_prompt()).exec()


if __name__ == "__main__":
    repo_path = os.environ.get("GIT_REPO", "")
    if repo_path:
        os.chdir(repo_path)
    GitMenu().exec()
