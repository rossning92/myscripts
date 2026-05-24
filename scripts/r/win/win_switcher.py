import time
from pathlib import Path
from typing import Dict, Optional

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
            prompt="activate", prompt_color="cyan", items=[], line_number=False
        )
        self.__auto_refresh_enabled = True
        self.__auto_refresh_last_time = 0.0
        self.script_status: Dict[str, str] = {}
        self.add_command(self.__refresh_windows, hotkey="ctrl+r")
        self.add_command(self.__close_windows, hotkey="delete")
        self.add_command(self.__close_windows, hotkey="ctrl+k")

        for i in range(26):
            self.add_command(
                lambda i=i: self.__activate_by_index(9 + i),
                hotkey=f"alt+{chr(ord('a') + i)}",
            )

        self.__refresh_windows()

    def __activate_by_index(self, index: int) -> bool:
        item_indices = list(self.get_item_indices())
        if index < len(item_indices):
            self.set_selected_row(index)
            self.__activate_window(self.items[item_indices[index]].id)
            return True
        return False

    def __refresh_windows(self, message: Optional[str] = None):
        notifications = get_notifications()
        self.script_status = {
            n["app"]: n.get("hint")
            for n in (notifications or [])
            if isinstance(n, dict) and isinstance(n.get("app"), str)
        }
        self.items = get_windows(script_status=self.script_status)

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

    def on_char(self, ch):
        if isinstance(ch, str) and ch.isdigit():
            index = int(ch) - 1
            if 0 <= index <= 8 and self.__activate_by_index(index):
                return True
        return super().on_char(ch)

    def on_focus_gained(self):
        self.__refresh_windows()
        self.__auto_refresh_enabled = True
        self.__auto_refresh_last_time = time.time()

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
        text = super().get_item_text(item)
        item_indices = self.get_item_indices()
        for i in range(min(35, len(item_indices))):
            if self.items[item_indices[i]] == item:
                if i < 9:
                    label = f" {i + 1}"
                else:
                    label = f"!{chr(ord('a') + i - 9)}"
                return f"[{label}] {text}"
        return "     " + text

    def get_item_color(self, item: WindowItem) -> str:
        status = item.get_status(self.script_status)
        return _STATUS_COLOR_MAPPING.get(status, "white")


if __name__ == "__main__":
    set_terminal_title(Path(__file__).stem)
    hide_terminal_from_taskbar()
    WinSwitcherMenu().exec()
