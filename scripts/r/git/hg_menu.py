import os
import subprocess

from utils.menu.diffmenu import DiffMenu

from git.vcs import get_hg_recent_commits, run_vcs
from git.vcs_menu import VcsDiffMenu


def _hg(*args):
    try:
        return subprocess.check_output(
            ["hg", *args], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except subprocess.CalledProcessError:
        return ""


def build_hg_diff_cmd(*extra_args):
    return [
        "hg",
        "diff",
        "-U10",
        "--color=always",
        "--config", "color.diff.inserted=green",
        "--config", "color.diff.deleted=red",
        *extra_args,
    ]


class HgMenu(VcsDiffMenu):
    _vcs = "hg"

    def _get_recent_commits(self):
        return get_hg_recent_commits()

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
        dirty_marker = "" if is_clean else " *"
        return f"{repo_name} ({bookmark}{dirty_marker})"

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
            run_vcs("hg", "revert", "--no-backup", "--", filename)

    def _commit_files(self, filenames, message, *, stage):
        cmds = [["hg", "add", "--"] + filenames] if stage else []
        cmds += [["hg", "commit", "-m", message, "--"] + filenames]
        self._run_shell_cmds(cmds)

    def __build_diff_cmd(self, *extra_args):
        return build_hg_diff_cmd(*extra_args)

    def _init_extra_commands(self):
        self.add_command(self._diff_incl_head)

    def _diff_incl_head(self):
        # Diff from the parent of the current commit through the working tree,
        # i.e. the current commit's own changes plus any uncommitted edits.
        diff_cmd = self.__build_diff_cmd("-r", ".^")
        DiffMenu(
            root=os.getcwd(), diff_cmd=diff_cmd, prompt_prefix=self.get_prompt()
        ).exec()

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
