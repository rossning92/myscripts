import sys
import time
from pathlib import Path
from typing import Dict, Optional, Set

from _pkgmanager import require_package
from utils.menu import Menu
from utils.notify import get_notifications
from utils.term import hide_terminal_from_taskbar, set_terminal_title
from utils.termux import is_in_termux
from utils.tmux import is_in_tmux
from utils.window import (
    WindowItem,
    WindowStatus,
    activate_window,
    close_window,
    get_windows,
)

_WINDOW_CLOSE_WAIT_SECONDS = 1.0
_AUTO_REFRESH_INTERVAL_SECONDS = 2.0
_PROMPT = "activate window"

_STATUS_COLOR_MAPPING: Dict[WindowStatus, str] = {
    "success": "green",
    "error": "red",
    "running": "yellow",
}


class WinSwitcherMenu(Menu[WindowItem]):
    def __init__(self):
        super().__init__(
            prompt=_PROMPT,
            items=[],
            line_number=False,
            quick_select=True,
            timeout_sec=_AUTO_REFRESH_INTERVAL_SECONDS,
        )
        self.__auto_refresh_enabled = True
        self.script_status: Dict[str, str] = {}
        self.__visited_success: Set[str] = set()
        self.__pinned: Set[str] = set()
        self.__has_item_markers = False
        self.add_command(self.__refresh_windows, hotkey="ctrl+r")
        self.add_command(self.__close_windows, hotkey="delete")
        self.add_command(self.__close_windows, hotkey="ctrl+k")
        self.add_command(self.__close_windows, hotkey="-")
        self.add_command(self.__toggle_pin, hotkey="ctrl+t", name="pin/unpin")

    def on_created(self):
        self.__refresh_windows()

    def __toggle_pin(self):
        titles = {item.title for item in self.get_selected_items()}
        if not titles:
            return
        if titles <= self.__pinned:
            self.__pinned -= titles
            self.set_message("unpinned")
        else:
            self.__pinned |= titles
            self.set_message("pinned")
        self.set_multi_select(False)
        self.__refresh_windows()

    def __get_sort_key(self, w: WindowItem) -> int:
        if w.title in self.__pinned:
            return 2
        status = w.get_status(self.script_status)
        if status == "success":
            return 0 if w.title not in self.__visited_success else 1
        if status == "running":
            return 3
        return 4

    def __refresh_windows(self, message: Optional[str] = None):
        begin, end = self.get_selected_row_range()
        selected = self.get_selected_item() if begin == end else None

        notifications = get_notifications()
        self.script_status = {
            n["app"]: n.get("hint")
            for n in (notifications or [])
            if isinstance(n, dict) and isinstance(n.get("app"), str)
        }
        self.items = get_windows(script_status=self.script_status)
        self.items.sort(key=self.__get_sort_key)

        current_success_titles = {
            w.title
            for w in self.items
            if w.get_status(self.script_status) == "success"
        }
        self.__visited_success &= current_success_titles
        self.__has_item_markers = any(
            self.__get_item_marker(item) for item in self.items
        )

        if message:
            self.set_message(message)
        self.refresh()

        if selected:
            for row, i in enumerate(self.get_item_indices()):
                if self.items[i].id == selected.id:
                    self.set_selected_row(row)
                    break

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
        if self.get_input() and self.get_row_count() == 0:
            self.clear_input()

    def on_enter_pressed(self):
        selected = self.get_selected_item()
        if selected:
            self.__activate_window(selected.id)
            if selected.get_status(self.script_status) == "success":
                self.__visited_success.add(selected.title)

    def on_focus_gained(self):
        self.__refresh_windows()
        self.__auto_refresh_enabled = True

    def on_focus_lost(self):
        self.__auto_refresh_enabled = False

    def on_timeout(self):
        if self.__auto_refresh_enabled:
            self.__refresh_windows()

    def on_escape_pressed(self):
        self.clear_input()

    def __get_item_marker(self, item: WindowItem) -> Optional[str]:
        if item.title in self.__pinned:
            return "★"
        status = item.get_status(self.script_status)
        if status == "success" and item.title not in self.__visited_success:
            return "●"
        return None

    def get_item_text(self, item: WindowItem) -> str:
        marker = self.__get_item_marker(item)
        prefix = f"{marker} " if marker else "  " if self.__has_item_markers else ""
        return prefix + item.title

    def get_item_color(self, item: WindowItem) -> str:
        if item.title in self.__pinned:
            return "cyan"
        status = item.get_status(self.script_status)
        return _STATUS_COLOR_MAPPING.get(status, "white")


if __name__ == "__main__":
    if sys.platform == "linux" and not (is_in_termux() or is_in_tmux()):
        require_package("wmctrl")

    set_terminal_title(Path(__file__).stem)
    hide_terminal_from_taskbar()
    WinSwitcherMenu().exec()
