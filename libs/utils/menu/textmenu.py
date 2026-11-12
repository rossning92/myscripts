import re
from typing import Optional

from .menu import Menu

_CODE_BG = "\x1b[48;5;236m"

# Inline markers and link targets are hidden, block markers (#, >, ```) are kept and colored.
_MARKDOWN = [
    # Links go first, since the escapes added by later rules contain "[".
    (re.compile(r"\[([^\]]+)\]\([^)]+\)"), "\x1b[38;5;39m\\1\x1b[39m"),
    (re.compile(r"<(?:https?|mailto):[^>]*>"), "\x1b[38;5;39m<link>\x1b[39m"),
    (re.compile(r"(\*\*|__)(.+?)\1"), "\x1b[1m\\2\x1b[22m"),
    (re.compile(r"`([^`]+)`"), f"\x1b[33m{_CODE_BG}\\1\x1b[39;49m"),
    (re.compile(r"^#{1,6} .*"), "\x1b[1;38;5;220m\\g<0>\x1b[22;39m"),
    (re.compile(r"^(>|```).*"), "\x1b[38;5;244m\\g<0>\x1b[39m"),
]


class _CodeLine(str):
    pass


class TextMenu(Menu[str]):
    def __init__(
        self,
        text: Optional[str] = None,
        file: Optional[str] = None,
        wrap_text=True,
        markdown=False,
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
        self.__markdown = markdown
        self.__in_fence = False
        assert file or text, "Either file or text needs to be provided"
        if file:
            with open(file, "r", encoding="utf-8") as f:
                text = f.read()
        for line in text.splitlines():
            self.items.append(self.__mark_code(line))

    def __mark_code(self, line: str) -> str:
        # Tags lines inside a ``` fence, since styling sees one line at a time.
        if self.__markdown and line.startswith("```"):
            self.__in_fence = not self.__in_fence
        elif self.__in_fence:
            return _CodeLine(line)
        return line

    def append_item(self, item: str):
        super().append_item(self.__mark_code(item))

    def clear_items(self):
        self.__in_fence = False
        super().clear_items()

    def search_by_input(self, save_search_history=True) -> bool:
        if super().search_by_input(save_search_history=save_search_history):
            self.__keyword = self.get_input()
            return True
        return False

    def get_item_text(self, item: str) -> str:
        if isinstance(item, _CodeLine):
            item = f"{_CODE_BG}{item}\x1b[49m"
        elif self.__markdown:
            for patt, repl in _MARKDOWN:
                item = patt.sub(repl, item)
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
        if self.get_input():
            self.clear_input()
            return
        line = self.get_selected_item()
        if line:
            from .contextmenu import ContextMenu

            ContextMenu(param=line).exec()
