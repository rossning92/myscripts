import re
from typing import Optional

from .menu import Menu


class TextMenu(Menu[str]):
    def __init__(
        self,
        text: Optional[str] = None,
        file: Optional[str] = None,
        wrap_text=True,
        **kwargs,
    ):
        super().__init__(
            close_on_selection=False,
            cancellable=True,
            fuzzy_search=False,
            search_on_enter=True,
            wrap_text=wrap_text,
            **kwargs,
        )
        self.__keyword = ""
        assert file or text, "Either file or text needs to be provided"
        if file:
            with open(file, "r", encoding="utf-8") as f:
                for line in f.read().splitlines():
                    self.items.append(line)
        elif text:
            for line in text.splitlines():
                self.items.append(line)

    def search_by_input(self, save_search_history=True) -> bool:
        if super().search_by_input(save_search_history=save_search_history):
            self.__keyword = self.get_input()
            return True
        return False

    def get_item_text(self, item: str) -> str:
        # Digits-only input jumps to a line number instead of filtering.
        if not self.__keyword or self.__keyword.isdigit():
            return item
        try:
            # Orange foreground + reverse renders as an orange background. 27;39 restores the item color.
            return re.sub(
                self.__keyword,
                "\x1b[38;5;208;7m\\g<0>\x1b[27;39m",
                item,
                flags=re.IGNORECASE,
            )
        except re.error:
            return item

    def get_item_metadata(self, item: str) -> str:
        return item

    def on_enter_pressed(self):
        if self.search_by_input():
            return
        else:
            self.clear_input()
