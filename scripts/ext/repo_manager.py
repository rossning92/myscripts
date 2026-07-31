import glob
import os
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from utils.jsonutil import load_json
from utils.menu.inputmenu import InputMenu
from utils.menu.menu import Menu
from utils.menu.shellcmdmenu import ShellCmdMenu
from utils.spinner import Spinner
from utils.script.path import get_my_script_root, get_script_dirs_config_file

from git.vcs import (
    get_amend_cmds,
    get_git_recent_commits,
    get_hg_recent_commits,
    prepend_recent_commits,
    run_vcs,
)

_MODULE_NAME = "repos"
_DEFAULT_COMMIT_MESSAGE = "commit with no message"


def _prompt_commit_message() -> Optional[str]:
    # Prompt for a commit message. Returns None if cancelled, or the default
    # message when the input is left empty.
    menu = InputMenu(prompt=f'Commit message (empty="{_DEFAULT_COMMIT_MESSAGE}"):', prompt_color="green")
    message = menu.request_input()
    if message is None:
        return None
    if not message.strip():
        return _DEFAULT_COMMIT_MESSAGE
    return message


class Repo:
    def __init__(self, path: str):
        self.path = path
        self.is_git = os.path.isdir(os.path.join(path, ".git"))
        self.is_hg = not self.is_git and os.path.isdir(os.path.join(path, ".hg"))
        self.branch: Optional[str] = None
        self.dirty = False
        self.ahead = 0
        self.behind = 0
        self.recent_commits: List[str] = []

    @property
    def vcs(self) -> Optional[str]:
        if self.is_git:
            return "git"
        if self.is_hg:
            return "hg"
        return None

    def refresh(self):
        if self.is_git:
            self._refresh_git()
        elif self.is_hg:
            self._refresh_hg()

    def _refresh_git(self):
        self.branch = "?"
        self.dirty = False
        self.ahead = self.behind = 0

        # One call yields branch, upstream tracking, ahead/behind and dirty,
        # replacing separate rev-parse + status + rev-list invocations.
        output = run_vcs(self.path, "git", "status", "--porcelain=v2", "--branch")
        if output:
            for line in output.splitlines():
                if line.startswith("# branch.head "):
                    self.branch = line[len("# branch.head ") :]
                elif line.startswith("# branch.ab "):
                    # Format: "# branch.ab +<ahead> -<behind>".
                    parts = line.split()
                    if len(parts) == 4:
                        self.ahead = int(parts[2].lstrip("+"))
                        self.behind = int(parts[3].lstrip("-"))
                elif not line.startswith("#"):
                    # Header lines precede file entries, so any non-header line
                    # means the worktree is dirty.
                    self.dirty = True
                    break

        self.recent_commits = get_git_recent_commits(self.path)

    def _refresh_hg(self):
        self.branch = run_vcs(
            self.path, "hg", "log", "-r", ".", "--template", "{activebookmark}"
        )
        if not self.branch:
            self.branch = (
                run_vcs(self.path, "hg", "log", "-r", ".", "--template", "{branch}")
                or "?"
            )

        status = run_vcs(self.path, "hg", "status")
        self.dirty = bool(status)

        self.ahead = self.behind = 0

        self.recent_commits = get_hg_recent_commits(self.path)

    @property
    def display_path(self) -> str:
        return self.path.replace(os.path.expanduser("~"), "~", 1)

    @property
    def vcs_info(self) -> str:
        if not self.vcs:
            return ""
        parts = [f"{self.vcs}:{self.branch}"]
        if self.dirty:
            parts.append("*")
        if self.ahead:
            parts.append(f"↑{self.ahead}")
        if self.behind:
            parts.append(f"↓{self.behind}")
        return " ".join(parts)

    def __str__(self) -> str:
        return self.display_path


def _get_repos() -> List[Repo]:
    dirs = [get_my_script_root()]
    config_file = get_script_dirs_config_file()
    data = load_json(config_file, default=[])
    seen_paths = {os.path.realpath(dirs[0])}

    extra_dirs = [entry["directory"] for entry in data]
    extra = os.environ.get("REPO_PATHS", "")
    extra_dirs += [d.strip() for d in extra.split(os.pathsep)]

    def _mtime(path: str) -> float:
        try:
            return os.path.getmtime(path)
        except OSError:
            return 0.0

    for d in extra_dirs:
        if not d:
            continue
        # Sort wildcard matches by directory modification time, newest first.
        for p in sorted(glob.glob(os.path.expanduser(d)), key=_mtime, reverse=True):
            if os.path.isabs(p) and os.path.isdir(p):
                real = os.path.realpath(p)
                if real not in seen_paths:
                    seen_paths.add(real)
                    dirs.append(p)
    return [Repo(d) for d in dirs]


class RepoMenu(Menu[Repo]):
    def __init__(self):
        super().__init__(
            cancellable=False,
            close_on_selection=False,
            prompt=_MODULE_NAME,
            quick_select=True,
        )
        self._refresh_thread: Optional[threading.Thread] = None
        self._spinner = Spinner()
        self._last_refresh_time = 0.0
        self._focused = True
        self.add_command(self._sync, hotkey="ctrl+s", name="sync", pinned=True)
        self.add_command(self._amend, hotkey="alt+a", name="amend", pinned=True)
        self.add_command(self._commit, hotkey="alt+c", name="commit", pinned=True)
        self.add_command(self._push, hotkey="alt+p", name="push", pinned=True)
        self.add_command(self._amend_and_push, hotkey="alt+a", name="amend+push")
        self.add_command(self._commit_and_sync, hotkey="alt+c", name="commit+sync")
        self.add_command(self._refresh, hotkey="ctrl+r", name="refresh", pinned=True)

    def get_item_text(self, item: Repo) -> str:
        vcs_info = item.vcs_info
        if vcs_info:
            width = self._max_path_width()
            return f"{item.display_path:<{width}}  {vcs_info}"
        return item.display_path

    def _max_path_width(self) -> int:
        return max(len(item.display_path) for item in self.items)

    def get_item_color(self, item: Repo) -> str:
        if not item.vcs:
            return "brightblack"
        if item.dirty or item.ahead:
            return "yellow"
        if item.behind:
            return "red"
        return super().get_item_color(item)

    def on_item_selected(self, item: Repo):
        if not item.vcs:
            return
        saved_cwd = os.getcwd()
        try:
            os.chdir(item.path)
            if item.is_git:
                from git.git_menu import GitMenu

                GitMenu(prompt_prefix=_MODULE_NAME).exec()
            elif item.is_hg:
                from git.hg_menu import HgMenu

                HgMenu(prompt_prefix=_MODULE_NAME).exec()
        finally:
            os.chdir(saved_cwd)
        self._refresh()

    def _run_cmds(self, *commands: List[str]):
        repo = self.get_selected_item()
        if repo is None or not repo.vcs:
            return

        shell_cmd = " && ".join(subprocess.list2cmdline(cmd) for cmd in commands)
        menu = ShellCmdMenu(
            shell_cmd,
            cwd=repo.path,
        )
        menu.exec()
        self._refresh()

    @staticmethod
    def _sync_cmds(repo: Repo) -> List[List[str]]:
        if repo.is_git:
            return [["git", "pull", "--rebase"], ["git", "push"]]
        elif repo.is_hg:
            return [["hg", "pull"], ["hg", "push"]]
        return []

    def _sync(self):
        repo = self.get_selected_item()
        if repo is None:
            return
        self._run_cmds(*self._sync_cmds(repo))

    def _amend(self, push: bool = False):
        repo = self.get_selected_item()
        if repo is None or not repo.vcs:
            return
        if push and repo.is_hg:
            self.set_message("amend+push is not supported for hg")
            return
        self._run_cmds(*get_amend_cmds(repo.vcs, push=push))

    def _push(self):
        repo = self.get_selected_item()
        if repo is None:
            return
        if repo.is_git:
            self._run_cmds(["git", "push"])
        elif repo.is_hg:
            self._run_cmds(["hg", "push"])

    def _amend_and_push(self):
        self._amend(push=True)

    def _commit(self, sync: bool = False):
        repo = self.get_selected_item()
        if repo is None or not repo.vcs:
            return
        message = _prompt_commit_message()
        if message is None:
            return
        if repo.is_git:
            # If something is already staged, commit only the staged files.
            # Otherwise fall back to staging everything.
            staged = run_vcs(repo.path, "git", "diff", "--cached", "--name-only")
            cmds = [] if staged else [["git", "add", "-A"]]
            cmds += [["git", "commit", "-m", message]]
        elif repo.is_hg:
            cmds = [["hg", "addremove"], ["hg", "commit", "-m", message]]
        else:
            return
        if sync:
            cmds += self._sync_cmds(repo)
        self._run_cmds(*cmds)

    def _commit_and_sync(self):
        self._commit(sync=True)

    def get_status_text(self) -> str:
        # Prepend recent commits of the selected repo on top of the default
        # status bar (message + position indicators).
        repo = self.get_selected_item()
        recent_commits = repo.recent_commits if repo is not None else []
        return prepend_recent_commits(super().get_status_text(), recent_commits)

    def on_created(self):
        self._refresh()

    def on_main_loop(self):
        if self._refresh_thread is not None:
            return

        # Auto-refresh every 10s, but only while the window is focused. to avoid
        # dragging system perf down when running unfocused in the background.
        if self._focused and time.monotonic() - self._last_refresh_time >= 10:
            self._refresh()

    def on_focus_gained(self):
        self._focused = True
        self._refresh()

    def on_focus_lost(self):
        self._focused = False

    def _refresh(self):
        if self._refresh_thread is not None:
            return
        self._last_refresh_time = time.monotonic()
        repos: Optional[List[Repo]] = None

        def worker():
            nonlocal repos
            repos = _get_repos()
            with ThreadPoolExecutor() as pool:
                pool.map(Repo.refresh, repos)

        self._refresh_thread = threading.Thread(target=worker, daemon=True)
        self._refresh_thread.start()
        while self._refresh_thread.is_alive():
            self.set_prompt(f"{_MODULE_NAME} {self._spinner.frame}")
            self._spinner.advance()
            self.process_events(timeout_sec=0.1)

        self._refresh_thread.join()
        self._refresh_thread = None
        self.set_prompt(_MODULE_NAME)
        if repos is not None:
            self.items[:] = repos
            self.update_screen()


if __name__ == "__main__":
    RepoMenu().exec()
