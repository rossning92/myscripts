import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Optional, Set

from _pkgmanager import require_package
from utils.markdown import strip_markdown
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
_MAX_TITLE_CHARS = 40
_COLUMN_SEPARATOR = " | "
# Caps option columns that have another column to their right.
_OPTION_WIDTH = 24

_STATUS_COLOR_MAPPING: Dict[WindowStatus, str] = {
    "success": "green",
    "waiting": "orange",
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
        self.__title_chars = 0
        self.__option_widths: Dict[str, int] = {}
        self.add_command(self.__refresh_windows, hotkey="ctrl+r")
        self.add_command(self.__close_windows, hotkey="delete")
        self.add_command(
            self.__close_windows,
            hotkey="ctrl+x",
            name="close",
            show_in_hotkey_bar=True,
        )
        self.add_command(self.__toggle_pin, hotkey="ctrl+t", name="pin/unpin")

    def on_created(self):
        self.on_focus_gained()

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
        if status == "waiting":
            return 0
        if status == "success":
            return 0 if w.title not in self.__visited_success else 1
        if status == "running":
            return 3
        return 4

    def __refresh_windows(
        self, message: Optional[str] = None, *, select_id: Optional[str] = None
    ):
        begin, end = self.get_selected_row_range()
        selected = self.get_selected_item() if begin == end else None

        notifications = get_notifications()
        self.script_status = {
            n["app"]: n.get("hint")
            for n in (notifications or [])
            if isinstance(n, dict) and isinstance(n.get("app"), str)
        }
        self.items = get_windows(script_status=self.script_status)
        for window in self.items:
            activity = window.options.get("@activity")
            if activity:
                window.options["@activity"] = next(
                    iter(strip_markdown(activity).splitlines()), ""
                )
        self.items.sort(key=self.__get_sort_key)
        names = sorted({name for w in self.items for name in w.options})
        self.__option_widths = {
            name: max(len(w.options.get(name, "")) for w in self.items)
            for name in names
        }
        for name in names[:-1]:
            self.__option_widths[name] = min(self.__option_widths[name], _OPTION_WIDTH)

        current_success_titles = {
            w.title
            for w in self.items
            if w.get_status(self.script_status) == "success"
        }
        self.__visited_success &= current_success_titles

        if message:
            self.set_message(message)
        self.refresh()

        rows = {self.items[i].id: row for row, i in enumerate(self.get_item_indices())}
        if select_id in rows:
            self.set_multi_select(False)
            self.set_selected_row(rows[select_id])
        elif selected and selected.id in rows:
            self.set_selected_row(rows[selected.id])

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
        self.clear_input()

    def on_focus_gained(self):
        previous_id = None
        if is_in_tmux() and (pane := os.environ.get("TMUX_PANE")):
            result = subprocess.run(
                [
                    "tmux",
                    "list-windows",
                    "-t",
                    pane,
                    "-f",
                    "#{window_last_flag}",
                    "-F",
                    "#{window_id}",
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and (window_id := result.stdout.strip()):
                previous_id = f"tmux:{window_id}"
        self.__refresh_windows(select_id=previous_id)
        self.__auto_refresh_enabled = True

    def on_focus_lost(self):
        self.__auto_refresh_enabled = False

    def on_timeout(self):
        if self.__auto_refresh_enabled:
            self.__refresh_windows()

    def on_escape_pressed(self):
        self.clear_input()

    def _update_screen(self):
        longest_title = max(
            (len(self.items[i].title) for i in self.get_item_indices()), default=0
        )
        self.__title_chars = min(longest_title, _MAX_TITLE_CHARS)
        super()._update_screen()

    def get_item_text(self, item: WindowItem) -> str:
        title = item.title[:_MAX_TITLE_CHARS]
        columns = [
            item.options.get(name, "")[:width].ljust(width)
            for name, width in self.__option_widths.items()
        ]
        while columns and not columns[-1].strip():
            columns.pop()
        options = _COLUMN_SEPARATOR.join(columns).rstrip()
        if options:
            title = title.ljust(self.__title_chars)
        if (
            item.get_status(self.script_status) == "success"
            and item.title not in self.__visited_success
        ):
            title = f"\x1b[1m{title}\x1b[22m"
        return f"{title}{_COLUMN_SEPARATOR}{options}" if options else title

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
