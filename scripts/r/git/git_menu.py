import os
import subprocess

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
                "status", "--short", "-u", universal_newlines=True
            )
            if status.strip():
                return status.splitlines(), False
            else:
                show_output = _git_output(
                    "show",
                    "--name-status",
                    "--format=",
                    "HEAD",
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
        elif item.startswith("??"):
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
