import os
import subprocess

from utils.menu.menu import Menu

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
    _rev = "."

    def _is_readonly(self):
        return self._rev != "."

    def _commit_choices(self):
        commits = get_hg_recent_commits()
        if not commits:
            return []
        return [(".", "(working copy)")] + [(c.split()[0], c) for c in commits]

    def _get_recent_commits(self):
        return [
            f"{'* ' if rev == self._rev else '  '}{label}"
            for rev, label in self._commit_choices()
        ]

    def _get_status_items(self):
        if self._rev == ".":
            status = _hg("status")
            if status:
                return status.splitlines(), False
        files = _hg("log", "-r", self._rev, "--template", "{files % '{file}\\n'}")
        items = [f"   {f}" for f in files.splitlines() if f.strip()]
        return items, True

    def _get_vcs_prompt(self, is_clean):
        repo_name = self._repo_display_name()
        bookmark = _hg("log", "-r", ".", "--template", "{activebookmark}")
        if not bookmark:
            bookmark = _hg("log", "-r", ".", "--template", "{branch}") or "?"
        if self._rev != ".":
            return f"{repo_name} ({bookmark}) [{self._rev}]"
        dirty_marker = "" if is_clean else " *"
        return f"{repo_name} ({bookmark}{dirty_marker})"

    def _select_commit(self):
        choices = self._commit_choices()
        idx = Menu(
            items=[label for _, label in choices],
            prompt="select commit",
            quick_select=True,
        ).exec()
        if idx < 0:
            return
        self._rev = choices[idx][0]
        self.set_selected_row(0)
        self._refresh()

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

    def _get_commit_cmds(self, filenames, message, *, stage):
        cmds = [["hg", "add", "--"] + filenames] if stage else []
        cmds += [["hg", "commit", "-m", message, "--"] + filenames]
        return cmds

    def __build_diff_cmd(self, *extra_args):
        return build_hg_diff_cmd(*extra_args)

    def _init_extra_commands(self):
        self.add_command(self._diff_incl_head)
        self.add_command(
            self._select_commit, hotkey="alt+s", name="select commit", pinned=True
        )

    def _diff_incl_head(self):
        # Diff from the parent of the current commit through the working tree,
        # i.e. the current commit's own changes plus any uncommitted edits.
        diff_cmd = self.__build_diff_cmd("-r", ".^")
        self._open_diff(root=os.getcwd(), diff_cmd=diff_cmd)

    def _diff_all(self):
        if self._is_clean:
            diff_cmd = self.__build_diff_cmd("-c", self._rev)
        else:
            diff_cmd = self.__build_diff_cmd()
        self._open_diff(root=os.getcwd(), diff_cmd=diff_cmd)

    def on_item_selected(self, item):
        filename = self._get_filename(item)
        if self._is_clean:
            diff_cmd = self.__build_diff_cmd("-c", self._rev, "--", filename)
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
        self._open_diff(root=os.getcwd(), diff_cmd=diff_cmd)


if __name__ == "__main__":
    repo_path = os.environ.get("HG_REPO", "")
    if repo_path:
        os.chdir(repo_path)
    HgMenu().exec()
