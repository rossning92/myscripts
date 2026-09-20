import os
import subprocess
from dataclasses import dataclass
from typing import List, Optional

from utils.menu.diffmenu import DiffMenu

from git.vcs import get_git_recent_commits, run_vcs
from git.vcs_menu import VcsDiffMenu


def _git_output(*args, **kwargs):
    """Run Git without escaping non-ASCII characters in pathnames."""
    # This runs while the menu owns the terminal.  stdout is captured by
    # check_output; capture stderr as well so warnings/errors cannot corrupt
    # the active TUI.
    kwargs.setdefault("stderr", subprocess.PIPE)
    return subprocess.check_output(
        ["git", "-c", "core.quotePath=false", *args], **kwargs
    )


@dataclass(frozen=True)
class GitStatusItem:
    status: str
    path: str
    old_path: Optional[str] = None

    def __str__(self):
        name = f"{self.old_path} -> {self.path}" if self.old_path else self.path
        return f"{self.status:<2} {name}"


def _parse_porcelain_status(output: str) -> List[GitStatusItem]:
    """Parse `git status --porcelain=v1 -z` without reparsing display text."""
    records = output.split("\0")
    items = []
    index = 0
    while index < len(records) and records[index]:
        record = records[index]
        status, path = record[:2], record[3:]
        old_path = None
        if "R" in status or "C" in status:
            index += 1
            old_path = records[index]
        items.append(GitStatusItem(status=status, path=path, old_path=old_path))
        index += 1
    return items


def _parse_name_status(output: str) -> List[GitStatusItem]:
    """Parse `git show --name-status -z`, including scored renames/copies."""
    records = output.split("\0")
    items = []
    index = 0
    while index < len(records) and records[index]:
        raw_status = records[index]
        index += 1
        old_path = None
        if raw_status[:1] in ("R", "C"):
            old_path = records[index]
            index += 1
        path = records[index]
        index += 1
        items.append(
            GitStatusItem(status=raw_status[:1], path=path, old_path=old_path)
        )
    return items


class GitMenu(VcsDiffMenu):
    _vcs = "git"

    def _get_recent_commits(self):
        return get_git_recent_commits()

    def _init_extra_commands(self):
        self.add_command(self.__stage, hotkey="ctrl+s", name="stage", pinned=True)
        self.add_command(self.__unstage, hotkey="alt+u", name="unstage", pinned=True)

    def _get_status_items(self):
        try:
            status = _git_output(
                "status", "--porcelain=v1", "-z", "-u", text=True
            )
            if status:
                return _parse_porcelain_status(status), False
            else:
                show_output = _git_output(
                    "show",
                    "--name-status",
                    "-z",
                    "--format=",
                    "HEAD",
                    text=True,
                )
                return _parse_name_status(show_output), True
        except subprocess.CalledProcessError:
            return [], False

    def _get_vcs_prompt(self, is_clean):
        repo_name = self._repo_display_name()
        try:
            branch = _git_output(
                "rev-parse",
                "--abbrev-ref",
                "HEAD",
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except subprocess.CalledProcessError:
            branch = "?"
        dirty_marker = "" if is_clean else " *"
        return f"{repo_name} ({branch}{dirty_marker})"

    def get_item_color(self, item):
        if self._is_clean:
            return super().get_item_color(item)
        status = item.status
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
        return item.path

    def _discard_file(self, item, filename):
        status = item.status
        if "?" in status:
            path = os.path.join(os.getcwd(), filename)
            if os.path.isdir(path):
                run_vcs("git", "clean", "-fd", "--", filename)
            else:
                os.remove(path)
        else:
            run_vcs("git", "checkout", "HEAD", "--", filename)

    def __stage(self):
        for item in self.get_selected_items():
            filename = self._get_filename(item)
            run_vcs("git", "add", "--", filename)
        self._after_action()

    def __unstage(self):
        for item in self.get_selected_items():
            filename = self._get_filename(item)
            run_vcs("git", "reset", "HEAD", "--", filename)
        self._after_action()

    def _resolve_commit_files(self, selected_filenames):
        staged = _git_output("diff", "--cached", "--name-only", text=True).splitlines()
        if staged:
            return staged, "staged", False
        return selected_filenames, "selected", True

    def _get_commit_cmds(self, filenames, message, *, stage):
        cmds = [["git", "add", "--"] + filenames] if stage else []
        cmds += [["git", "commit", "-m", message]]
        return cmds

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
        elif item.status == "??":
            DiffMenu(
                untracked_file=filename, prompt_prefix=self.get_prompt()
            ).exec()
            return
        else:
            git_args = [filename]
        DiffMenu(git_args=git_args, prompt_prefix=self.get_prompt()).exec()


if __name__ == "__main__":
    repo_path = os.environ.get("GIT_REPO", "")
    if repo_path:
        os.chdir(repo_path)
    GitMenu().exec()
