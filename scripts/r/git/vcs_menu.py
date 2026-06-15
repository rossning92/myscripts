import os
import threading
import time
from typing import List, Optional, Tuple

from utils.menu.confirmmenu import confirm
from utils.menu.inputmenu import InputMenu
from utils.menu.menu import Menu


def _default_commit_message(filenames: List[str]) -> str:
    return "update " + ", ".join(os.path.basename(f) for f in filenames)


class VcsDiffMenu(Menu):
    def __init__(self, prompt_prefix: str = ""):
        super().__init__(close_on_selection=False, quick_select=True)
        self.__prompt_prefix = prompt_prefix
        self.__last_refresh_time = 0.0
        self.__refresh_thread: Optional[threading.Thread] = None
        self._is_clean: bool = False
        self.add_command(
            self._diff_all, hotkey="ctrl+a", name="diff all", pinned=True
        )
        self._init_extra_commands()
        self.add_command(self.__discard, hotkey="ctrl+d", name="discard", pinned=True)
        self.add_command(self.__commit, hotkey="alt+c", name="commit", pinned=True)
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
            prompt = f"{self.__prompt_prefix} > {prompt}"
        super().set_prompt(prompt)

    def _refresh(self) -> None:
        if self.__refresh_thread and self.__refresh_thread.is_alive():
            return
        self.__last_refresh_time = time.monotonic()

        def worker():
            items, is_clean = self._get_status_items()
            prompt = self._get_vcs_prompt(is_clean)
            self.post_event(lambda: self.__apply_refresh(items, is_clean, prompt))

        self.set_message("refreshing...")
        self.__refresh_thread = threading.Thread(target=worker, daemon=True)
        self.__refresh_thread.start()

    def __apply_refresh(self, items: List[str], is_clean: bool, prompt: str) -> None:
        self._is_clean = is_clean
        self.set_prompt(prompt if is_clean else f"\x1b[33m{prompt}\x1b[0m")
        self.items[:] = items
        self.set_message("refreshed")

    def on_idle(self) -> None:
        if time.monotonic() - self.__last_refresh_time >= 10:
            self._refresh()

    def _after_action(self) -> None:
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
