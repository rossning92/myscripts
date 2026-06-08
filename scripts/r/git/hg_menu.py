import os
import subprocess

from utils.menu.diffmenu import DiffMenu
from utils.menu.shellcmdmenu import ShellCmdMenu

from git.vcs_menu import VcsDiffMenu


def _hg(*args):
    try:
        return subprocess.check_output(
            ["hg", *args], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except subprocess.CalledProcessError:
        return ""


class HgMenu(VcsDiffMenu):
    _HOTKEY_HINTS = "--- [^a]diff all [^d]discard [!c]commit [^r]refresh ---"

    def _get_status_items(self):
        status = _hg("status")
        if status:
            return status.splitlines(), False
        files = _hg("log", "-r", ".", "--template", "{files % '{file}\\n'}")
        items = [f"   {f}" for f in files.splitlines() if f.strip()]
        return items, True

    def _get_vcs_prompt(self, is_clean):
        repo_name = self._repo_display_name()
        bookmark = _hg("log", "-r", ".", "--template", "{activebookmark}")
        if not bookmark:
            bookmark = _hg("log", "-r", ".", "--template", "{branch}") or "?"
        if is_clean:
            commit_info = _hg(
                "log", "-r", ".", "--template", "{short(node)} {desc|firstline}"
            )
            if commit_info:
                return f"{repo_name} ({bookmark}) {commit_info}"
            return f"{repo_name} ({bookmark})"
        return f"{repo_name} ({bookmark} *)"

    def get_item_color(self, item):
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

    def _get_filename(self, item):
        return item[2:].strip()

    def _discard_file(self, item, filename):
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

    def _commit_files(self, filenames, message):
        cmds = [["hg", "add", "--"] + filenames, ["hg", "commit", "-m", message, "--"] + filenames]
        shell_cmd = " && ".join(subprocess.list2cmdline(cmd) for cmd in cmds)
        ShellCmdMenu(shell_cmd).exec()

    def __build_diff_cmd(self, *extra_args):
        cmd = [
            "hg",
            "diff",
            "-U10",
            "--color=always",
            "--config", "color.diff.inserted=green",
            "--config", "color.diff.deleted=red",
        ]
        cmd.extend(extra_args)
        return cmd

    def _diff_all(self):
        if self._is_clean:
            diff_cmd = self.__build_diff_cmd("-c", ".")
        else:
            diff_cmd = self.__build_diff_cmd()
        DiffMenu(root=os.getcwd(), diff_cmd=diff_cmd, prompt_prefix=self.get_prompt()).exec()

    def on_item_selected(self, item):
        filename = self._get_filename(item)
        if self._is_clean:
            diff_cmd = self.__build_diff_cmd("-c", ".", "--", filename)
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
            diff_cmd = self.__build_diff_cmd("--", filename)
        DiffMenu(root=os.getcwd(), diff_cmd=diff_cmd, prompt_prefix=self.get_prompt()).exec()


if __name__ == "__main__":
    repo_path = os.environ.get("HG_REPO", "")
    if repo_path:
        os.chdir(repo_path)
    HgMenu().exec()
