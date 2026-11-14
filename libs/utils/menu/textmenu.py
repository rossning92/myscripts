import os
import re
import time
import unicodedata
from itertools import zip_longest
from typing import Optional

from utils.strutil import strip_ansi

from .menu import Menu

_CODE_BG = "\x1b[48;5;236m"

# Heading and inline markers are hidden; quote and fence markers stay visible.
_MARKDOWN = [
    # Links go first, since the escapes added by later rules contain "[".
    (re.compile(r"\[([^\]]+)\]\([^)]+\)"), "\x1b[38;5;39m\\1\x1b[39m"),
    (re.compile(r"<(?:https?|mailto):[^>]*>"), "\x1b[38;5;39m<link>\x1b[39m"),
    (re.compile(r"(\*\*|__)(.+?)\1"), "\x1b[1m\\2\x1b[22m"),
    (re.compile(r"`([^`]+)`"), f"\x1b[33m{_CODE_BG}\\1\x1b[39;49m"),
    (re.compile(r"^#{1,6} (.*)"), "\x1b[1;38;5;220m\\1\x1b[22;39m"),
    (re.compile(r"^(>|```).*"), "\x1b[38;5;244m\\g<0>\x1b[39m"),
]


class _CodeLine(str):
    pass


class _TableLine(str):
    rendered: str

    def __new__(cls, source: str, rendered: str):
        line = super().__new__(cls, source)
        line.rendered = rendered
        return line


class _TableExtraLine(_TableLine):
    pass


def _format_markdown(text: str) -> str:
    for patt, repl in _MARKDOWN:
        text = patt.sub(repl, text)
    return text


def _table_cells(line: str) -> list[str]:
    cells = re.split(r"(?<!\\)\|", line.strip())
    if not cells[0]:
        cells.pop(0)
    if cells and not cells[-1]:
        cells.pop()
    return [cell.strip().replace(r"\|", "|") for cell in cells]


def _text_width(text: str) -> int:
    return sum(
        0 if unicodedata.combining(char)
        else 2 if unicodedata.east_asian_width(char) in ("W", "F")
        else 1
        for char in strip_ansi(text)
    )


def _wrap_cell(text: str, width: int) -> list[str]:
    lines = []
    line = ""
    for word in text.split():
        if line and _text_width(line + " " + word) <= width:
            line += " " + word
            continue
        if line:
            lines.append(line)
            line = ""
        for char in word:
            if line and _text_width(line + char) > width:
                lines.append(line)
                line = ""
            line += char
    if line:
        lines.append(line)
    return lines or [""]


def _table_separator(line: str) -> bool:
    cells = _table_cells(line)
    return (
        not isinstance(line, _CodeLine)
        and "|" in line
        and bool(cells)
        and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)
    )


def _render_table(rows: list[list[str]], alignments: list[str], max_width: int):
    rows = [[strip_ansi(_format_markdown(cell)) for cell in row] for row in rows]
    widths = [
        min(max_width, max(1, max(_text_width(row[col]) for row in rows)))
        for col in range(len(alignments))
    ]
    segments = ["\u2500" * width for width in widths]
    top = "\u250c" + "\u252c".join(segments) + "\u2510"
    divider = "\u251c" + "\u253c".join(segments) + "\u2524"
    bottom = "\u2514" + "\u2534".join(segments) + "\u2518"
    rendered_rows = []
    for row in rows:
        wrapped = [_wrap_cell(cell, width) for cell, width in zip(row, widths)]
        rendered_lines = []
        for line in zip_longest(*wrapped, fillvalue=""):
            padded = []
            for cell, width, alignment in zip(line, widths, alignments):
                padding = width - _text_width(cell)
                left = padding if alignment.endswith(":") else 0
                if alignment.startswith(":") and alignment.endswith(":"):
                    left = padding // 2
                padded.append(" " * left + cell + " " * (padding - left))
            rendered = "\u2502" + "\u2502".join(padded) + "\u2502"
            rendered_lines.append(rendered)
        rendered_rows.append(rendered_lines)
    return top, divider, bottom, rendered_rows


class TextMenu(Menu[str]):
    def __init__(
        self,
        text: Optional[str] = None,
        file: Optional[str] = None,
        wrap_text=True,
        markdown=False,
        max_column_width=24,
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
        if max_column_width < 2:
            raise ValueError("max_column_width must be at least 2")
        self.__max_column_width = max_column_width
        self.__in_fence = False
        self.__file = os.path.abspath(file) if file else None
        if self.__file and (self.timeout_sec < 0 or self.timeout_sec > 1):
            self.timeout_sec = 1.0
        self.__file_version = None
        self.__last_file_check = 0.0
        assert file or text, "Either file or text needs to be provided"
        if self.__file:
            with open(self.__file, "r", encoding="utf-8") as f:
                self.__file_version = self.__version(os.fstat(f.fileno()))
                text = f.read()
        self.__load_text(text)

    @staticmethod
    def __version(stat):
        return stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size, stat.st_ino

    def __load_text(self, text: str):
        self.__in_fence = False
        self.items.clear()
        for line in text.splitlines():
            self.items.append(self.__mark_code(line))
        if self.__markdown:
            self.__format_tables()

    def on_main_loop(self):
        super().on_main_loop()
        if not self.__file or time.monotonic() - self.__last_file_check < 1:
            return
        self.__last_file_check = time.monotonic()
        try:
            if self.__version(os.stat(self.__file)) == self.__file_version:
                return
            with open(self.__file, "r", encoding="utf-8") as f:
                version = self.__version(os.fstat(f.fileno()))
                text = f.read()
                if self.__version(os.fstat(f.fileno())) != version:
                    return
        except (OSError, UnicodeError):
            # Keep the current view while an editor replaces or rewrites the file.
            return
        self.__load_text(text)
        self.__file_version = version
        self.refresh()

    def __mark_code(self, line: str) -> str:
        # Tags lines inside a ``` fence, since styling sees one line at a time.
        if self.__markdown and line.startswith("```"):
            self.__in_fence = not self.__in_fence
        elif self.__in_fence:
            return _CodeLine(line)
        return line

    def append_item(self, item: str):
        super().append_item(self.__mark_code(item))
        if self.__markdown:
            self.__format_tables()
            self.refresh()

    def clear_items(self):
        self.__in_fence = False
        super().clear_items()

    def search_by_input(self, save_search_history=True) -> bool:
        if super().search_by_input(save_search_history=save_search_history):
            self.__keyword = self.get_input()
            return True
        return False

    def __format_tables(self):
        # Rebuild from source lines so appended rows cannot duplicate decorations.
        source = [
            str(item) if isinstance(item, _TableLine) else item
            for item in self.items if not isinstance(item, _TableExtraLine)
        ]
        items = []
        i = 0
        while i < len(source):
            if (
                i + 1 >= len(source)
                or isinstance(source[i], _CodeLine)
                or "|" not in source[i]
                or not _table_separator(source[i + 1])
                or len(_table_cells(source[i])) != len(_table_cells(source[i + 1]))
            ):
                items.append(source[i])
                i += 1
                continue
            alignments = _table_cells(source[i + 1])
            rows = [_table_cells(source[i])]
            end = i + 2
            while end < len(source):
                line = source[end]
                if (
                    isinstance(line, _CodeLine)
                    or "|" not in line
                    or (end + 1 < len(source) and _table_separator(source[end + 1]))
                ):
                    break
                cells = _table_cells(line)
                if len(cells) != len(alignments):
                    break
                rows.append(cells)
                end += 1
            top, divider, bottom, rendered_rows = _render_table(
                rows, alignments, self.__max_column_width
            )
            items.append(_TableExtraLine("", top))
            source_rows = [source[i], *source[i + 2:end]]
            for row_index, (original, lines) in enumerate(zip(source_rows, rendered_rows)):
                items.append(_TableLine(original, lines[0]))
                items.extend(_TableExtraLine("", line) for line in lines[1:])
                if row_index == 0:
                    items.append(_TableLine(source[i + 1], divider))
            items.append(_TableExtraLine("", bottom))
            i = end
        self.items[:] = items

    def item_wrap(self, item: str) -> bool:
        return False if isinstance(item, _TableLine) else super().item_wrap(item)

    def get_item_text(self, item: str) -> str:
        if isinstance(item, _TableLine):
            item = item.rendered
        elif isinstance(item, _CodeLine):
            item = f"{_CODE_BG}{item}\x1b[49m"
        elif self.__markdown:
            item = _format_markdown(item)
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
