import time
from pathlib import Path
from typing import Dict, Optional, Set

from utils.menu import Menu
from utils.notify import get_notifications
from utils.term import hide_terminal_from_taskbar, set_terminal_title
from utils.window import (
    WindowItem,
    WindowStatus,
    activate_window,
    close_window,
    get_windows,
)

_WINDOW_CLOSE_WAIT_SECONDS = 1.0
_AUTO_REFRESH_INTERVAL_SECONDS = 2.0

_STATUS_COLOR_MAPPING: Dict[WindowStatus, str] = {
    "done": "green",
    "error": "red",
    "running": "yellow",
}


class WinSwitcherMenu(Menu[WindowItem]):
    def __init__(self):
        super().__init__(
            prompt="activate",
            items=[],
            line_number=False,
            quick_select=True,
        )
        self.__auto_refresh_enabled = True
        self.__auto_refresh_last_time = 0.0
        self.script_status: Dict[str, str] = {}
        self.__visited_done: Set[str] = set()
        self.__pinned: Set[str] = set()
        self.add_command(self.__refresh_windows, hotkey="ctrl+r")
        self.add_command(self.__close_windows, hotkey="delete")
        self.add_command(self.__close_windows, hotkey="ctrl+k")
        self.add_command(self.__toggle_pin, hotkey="ctrl+t", name="pin/unpin")

        self.__refresh_windows()

    def __toggle_pin(self):
        selected = self.get_selected_item(ignore_cancellation=True)
        if not selected:
            return
        if selected.title in self.__pinned:
            self.__pinned.discard(selected.title)
            self.set_message("unpinned")
        else:
            self.__pinned.add(selected.title)
            self.set_message("pinned")
        self.__refresh_windows()

    def __refresh_windows(self, message: Optional[str] = None):
        notifications = get_notifications()
        self.script_status = {
            n["app"]: n.get("hint")
            for n in (notifications or [])
            if isinstance(n, dict) and isinstance(n.get("app"), str)
        }
        self.items = get_windows(script_status=self.script_status)
        self.items.sort(
            key=lambda w: (0 if w.title in self.__pinned else 1,)
        )

        current_done_titles = {
            w.title for w in self.items if w.get_status(self.script_status) == "done"
        }
        self.__visited_done &= current_done_titles

        if message:
            self.set_message(message)
        else:
            self.set_message("refreshed")
        self.refresh()

    def __activate_window(self, win_id):
        error = activate_window(win_id)
        if error:
            self.set_message(error)

    def __close_window_by_id(self, win_id) -> Optional[str]:
        return close_window(win_id)

    def __close_windows(self):
        selected_items = list(self.get_selected_items())
        if not selected_items:
            return

        first_row, _ = self.get_selected_row_range()

        error = None
        win_ids_to_wait = []
        for selected in reversed(selected_items):
            err = self.__close_window_by_id(selected.id)
            if err:
                error = err
            else:
                win_ids_to_wait.append(selected.id)

        # Wait briefly for the windows to close
        if win_ids_to_wait:
            timeout = time.time() + _WINDOW_CLOSE_WAIT_SECONDS
            while time.time() < timeout:
                current_ids = {w.id for w in get_windows()}
                win_ids_to_wait = [wid for wid in win_ids_to_wait if wid in current_ids]
                if not win_ids_to_wait:
                    break
                time.sleep(0.1)

        self.set_multi_select(False)
        self.set_selected_row(first_row)
        self.__refresh_windows(message=error)

    def on_enter_pressed(self):
        selected = self.get_selected_item()
        if selected:
            self.__activate_window(selected.id)
            if selected.get_status(self.script_status) == "done":
                self.__visited_done.add(selected.title)

    def on_focus_gained(self):
        self.__refresh_windows()
        self.__auto_refresh_enabled = True
        self.__auto_refresh_last_time = time.time()
        self.__highlight_first_done()

    def __highlight_first_done(self):
        for item in self.items:
            if item.title in self.__pinned:
                continue
            if item.get_status(self.script_status) == "done":
                self.set_selected_item(item)
                break

    def on_focus_lost(self):
        self.__auto_refresh_enabled = False

    def on_idle(self):
        now = time.time()
        if (
            self.__auto_refresh_enabled
            and now > self.__auto_refresh_last_time + _AUTO_REFRESH_INTERVAL_SECONDS
        ):
            self.__auto_refresh_last_time = now
            self.__refresh_windows()

    def on_escape_pressed(self):
        self.clear_input()

    def get_item_text(self, item: WindowItem) -> str:
        if item.title in self.__pinned:
            return "★ " + item.title
        status = item.get_status(self.script_status)
        if status == "done" and item.title not in self.__visited_done:
            return "● " + item.title
        return item.title

    def get_item_color(self, item: WindowItem) -> str:
        if item.title in self.__pinned:
            return "cyan"
        status = item.get_status(self.script_status)
        return _STATUS_COLOR_MAPPING.get(status, "white")


if __name__ == "__main__":
    set_terminal_title(Path(__file__).stem)
    hide_terminal_from_taskbar()
    WinSwitcherMenu().exec()
