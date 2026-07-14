import os
import subprocess
import threading
import time
from itertools import cycle
from typing import List, Optional, Tuple

from utils.menu.confirmmenu import confirm
from utils.menu.inputmenu import InputMenu
from utils.menu.menu import Menu
from utils.menu.shellcmdmenu import ShellCmdMenu

from git.vcs import get_amend_cmds, prepend_recent_commits


def _default_commit_message(filenames: List[str]) -> str:
    return "update " + ", ".join(os.path.basename(f) for f in filenames)


class VcsDiffMenu(Menu):
    _vcs: str = ""

    def __init__(self, prompt_prefix: str = ""):
        super().__init__(close_on_selection=False, quick_select=True)
        self.__prompt_prefix = prompt_prefix
        self.__last_refresh_time = 0.0
        self.__refresh_thread: Optional[threading.Thread] = None
        self.__spinner = cycle(["|", "/", "-", "\\"])
        self.__base_prompt = os.path.basename(os.getcwd())
        self.__recent_commits: List[str] = []
        self._is_clean: bool = False
        self.add_command(
            self._diff_all, hotkey="ctrl+a", name="diff all", pinned=True
        )
        self._init_extra_commands()
        self.add_command(self.__discard, hotkey="ctrl+d", name="discard", pinned=True)
        self.add_command(self.__commit, hotkey="alt+c", name="commit", pinned=True)
        self.add_command(self.__amend, hotkey="alt+a", name="amend", pinned=True)
        self.add_command(self.__amend_and_push, hotkey="alt+a", name="amend+push")
        self.add_command(self._refresh, hotkey="ctrl+r", name="refresh", pinned=True)
        self.set_prompt(os.path.basename(os.getcwd()))
        self._refresh()

    def _init_extra_commands(self) -> None:
        pass

    def _get_status_items(self) -> Tuple[List[str], bool]:
        raise NotImplementedError

    def _repo_display_name(self) -> str:
        return os.getcwd().replace(os.path.expanduser("~"), "~", 1)

    def _get_vcs_prompt(self, is_clean: bool) -> str:
        raise NotImplementedError

    def _get_recent_commits(self) -> List[str]:
        return []

    def _get_filename(self, item: str) -> str:
        raise NotImplementedError

    def _discard_file(self, item: str, filename: str) -> None:
        raise NotImplementedError

    def _commit_files(
        self, filenames: List[str], message: str, *, stage: bool
    ) -> None:
        raise NotImplementedError

    def _resolve_commit_files(
        self, selected_filenames: List[str]
    ) -> Tuple[List[str], str, bool]:
        # Subclasses can override to substitute the files actually being
        # committed (e.g. already-staged files). Returns
        # (filenames, label, needs_staging).
        return selected_filenames, "selected", True

    def _diff_all(self) -> None:
        raise NotImplementedError

    def set_prompt(self, prompt: str) -> None:
        if self.__prompt_prefix:
            prompt = f"{self.__prompt_prefix} ❯ {prompt}"
        super().set_prompt(prompt)

    def _refresh(self) -> None:
        if self.__refresh_thread and self.__refresh_thread.is_alive():
            return
        self.__last_refresh_time = time.monotonic()

        def worker():
            items, is_clean = self._get_status_items()
            prompt = self._get_vcs_prompt(is_clean)
            recent_commits = self._get_recent_commits()
            self.post_event(
                lambda: self.__apply_refresh(items, is_clean, prompt, recent_commits)
            )

        self.__refresh_thread = threading.Thread(target=worker, daemon=True)
        self.__refresh_thread.start()

    def __apply_refresh(
        self,
        items: List[str],
        is_clean: bool,
        prompt: str,
        recent_commits: List[str],
    ) -> None:
        self._is_clean = is_clean
        self.__base_prompt = prompt if is_clean else f"\x1b[33m{prompt}\x1b[0m"
        self.__recent_commits = recent_commits
        self.set_prompt(self.__base_prompt)
        self.items[:] = items

    def get_status_text(self) -> str:
        return prepend_recent_commits(super().get_status_text(), self.__recent_commits)

    def on_idle(self) -> None:
        # Animate the prompt while the background refresh runs so a slow refresh
        # does not look idle.
        if self.__refresh_thread and self.__refresh_thread.is_alive():
            self.set_prompt(f"{self.__base_prompt} {next(self.__spinner)}")
            return
        if time.monotonic() - self.__last_refresh_time >= 10:
            self._refresh()

    def _after_action(self) -> None:
        # Collapse to the first row of the selection instead of the last so the
        # cursor lands where the selection started, which is more intuitive.
        begin, _ = self.get_selected_row_range()
        self.set_selected_row(begin)
        self.set_multi_select(False)
        self._refresh()

    def __commit(self) -> None:
        items = list(self.get_selected_items())
        if not items:
            return
        selected = [self._get_filename(item) for item in items]
        filenames, source, stage = self._resolve_commit_files(selected)
        if not filenames:
            return
        default_message = _default_commit_message(filenames)
        label = (
            f"Commit {len(filenames)} {source} file(s) "
            f'(empty="{default_message}")'
        )
        menu = InputMenu(prompt=label, prompt_color="green")
        message = menu.request_input()
        if message is None:
            return
        if not message.strip():
            message = default_message
        self._commit_files(filenames, message, stage=stage)
        self._after_action()

    def _run_shell_cmds(self, cmds: List[List[str]]) -> None:
        shell_cmd = " && ".join(subprocess.list2cmdline(cmd) for cmd in cmds)
        ShellCmdMenu(shell_cmd).exec()

    def __amend(self, push: bool = False) -> None:
        if push and self._vcs == "hg":
            self.set_message("amend+push is not supported for hg")
            return
        cmds = get_amend_cmds(self._vcs, push=push)
        if not cmds:
            return
        self._run_shell_cmds(cmds)
        self._after_action()

    def __amend_and_push(self) -> None:
        self.__amend(push=True)

    def __discard(self) -> None:
        items = list(self.get_selected_items())
        if not items:
            return
        names = [self._get_filename(item) for item in items]
        if not confirm(f"Discard changes to {len(names)} file(s)?", prompt_color="red"):
            return
        for item, filename in zip(items, names):
            self._discard_file(item, filename)
        self._after_action()
