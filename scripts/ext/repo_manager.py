import os
import subprocess
import time
from typing import List, Optional

from utils.jsonutil import load_json
from utils.menu.menu import Menu
from utils.script.path import get_my_script_root, get_script_dirs_config_file

_HOTKEY_HINTS = "--- [!c]commit+sync [!a]amend+sync [^r]refresh [^s]sync ---"


def _git(path: str, *args: str) -> Optional[str]:
    try:
        r = subprocess.run(
            ["git", *args],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


class Repo:
    def __init__(self, path: str):
        self.path = path
        self.is_git = os.path.isdir(os.path.join(path, ".git"))
        self.branch: Optional[str] = None
        self.dirty = False
        self.ahead = 0
        self.behind = 0

    def refresh(self):
        if not self.is_git:
            return

        self.branch = _git(self.path, "rev-parse", "--abbrev-ref", "HEAD") or "?"

        status = _git(self.path, "status", "--porcelain")
        self.dirty = bool(status)

        self.ahead = self.behind = 0
        counts = _git(
            self.path,
            "rev-list",
            "--left-right",
            "--count",
            f"{self.branch}...@{{u}}",
        )
        if counts:
            parts = counts.split()
            if len(parts) == 2:
                self.ahead, self.behind = int(parts[0]), int(parts[1])

    def __str__(self) -> str:
        if not self.is_git:
            return f"{self.path}  (not a git repo)"

        tags = []
        if self.dirty:
            tags.append("modified")
        if self.ahead:
            tags.append(f"↑{self.ahead}")
        if self.behind:
            tags.append(f"↓{self.behind}")

        return f"{self.path}  [{self.branch}]  {' '.join(tags) or 'clean'}"


def _get_repos() -> List[Repo]:
    dirs = [get_my_script_root()]
    config_file = get_script_dirs_config_file()
    data = load_json(config_file, default=[])
    seen_paths = {os.path.realpath(dirs[0])}
    for entry in data:
        d = entry["directory"]
        if os.path.isabs(d) and os.path.isdir(d):
            real = os.path.realpath(d)
            if real not in seen_paths:
                seen_paths.add(real)
                dirs.append(d)
    return [Repo(d) for d in dirs]


class RepoMenu(Menu[Repo]):
    def __init__(self):
        super().__init__(
            cancellable=False,
            close_on_selection=False,
            prompt="Repos",
        )
        self.set_header(_HOTKEY_HINTS)
        self._last_refresh_time = 0.0
        self._refresh()
        self.add_command(self._sync, hotkey="ctrl+s", name="Sync (pull+push)")
        self.add_command(self._amend_and_sync, hotkey="alt+a", name="Amend+sync")
        self.add_command(self._commit_and_sync, hotkey="alt+c", name="Commit+sync")
        self.add_command(self._refresh, hotkey="ctrl+r", name="Refresh")

    def get_item_color(self, item: Repo) -> str:
        if not item.is_git:
            return "brightblack"
        if item.dirty or item.ahead:
            return "yellow"
        if item.behind:
            return "red"
        return super().get_item_color(item)

    def on_item_selected(self, item: Repo):
        if not item.is_git:
            return
        saved_cwd = os.getcwd()
        try:
            os.chdir(item.path)
            from git.git_diff import GitMenu

            GitMenu().exec()
        finally:
            os.chdir(saved_cwd)
        self._refresh()

    def _run_git(self, *commands: List[str]):
        repo = self.get_selected_item()
        if repo is None or not repo.is_git:
            return

        def run():
            failed = False
            for cmd in commands:
                r = subprocess.run(cmd, cwd=repo.path, check=False)
                if r.returncode != 0:
                    failed = True
                    break
            if failed:
                input("\nPress Enter to continue...")

        self.run_raw(run)
        self._refresh()

    def _sync(self):
        self._run_git(
            ["git", "pull", "--rebase"],
            ["git", "push"],
        )

    def _amend_and_sync(self):
        self._run_git(
            ["git", "add", "-A"],
            ["git", "commit", "--amend", "--no-edit"],
            ["git", "push", "--force-with-lease"],
        )

    def _commit_and_sync(self):
        self._run_git(
            ["git", "add", "-A"],
            ["git", "commit", "-m", "commit with no message"],
            ["git", "pull", "--rebase"],
            ["git", "push"],
        )

    def on_idle(self):
        if time.monotonic() - self._last_refresh_time >= 30:
            self._refresh()

    def _refresh(self):
        self._last_refresh_time = time.monotonic()
        self.items.clear()
        for repo in _get_repos():
            repo.refresh()
            self.items.append(repo)
        self.update_screen()


if __name__ == "__main__":
    RepoMenu().exec()
