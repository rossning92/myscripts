import curses
import curses.ascii
import logging
import logging.handlers
import os
import re
import subprocess
import sys
import tempfile
import time
from queue import Queue
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    NamedTuple,
    Optional,
    OrderedDict,
    Tuple,
    TypeVar,
    Union,
)

from _shutil import get_hotkey_abbr

from utils.clamp import clamp
from utils.clip import get_clip, set_clip
from utils.editor import edit_text
from utils.jsonutil import load_json, save_json
from utils.slugify import slugify
from utils.term import enable_windows_vt

EXPERIMENTAL_EANBLE_WINDOWS_VT = True

GUTTER_SIZE = 1
PASTE_THRESHOLD_SEC = 0.05
PROCESS_EVENT_INTERVAL_SEC = 0.1
SHIFT_DOWN = 0x150
SHIFT_UP = 0x151
KEY_A2 = 450
KEY_C2 = 456
KEY_FOCUS_IN = 578
KEY_FOCUS_OUT = 579


def _clamp(n, smallest, largest):
    return max(smallest, min(n, largest))


def _is_backspace_key(ch: Union[int, str]):
    return (
        ch == curses.KEY_BACKSPACE
        or ch == "\b"  # for windows
        or ch == "\x7f"  # for mac and linux
    )


def _decode_escape_sequence(stdscr, ch: Union[int, str]) -> Union[int, str]:
    if isinstance(ch, int):
        try:
            name = curses.keyname(ch).decode()
            if name == "kLFT5":
                return "ctrl+left"
            elif name == "kRIT5":
                return "ctrl+right"
            elif name == "kLFT3":
                return "alt+left"
            elif name == "kRIT3":
                return "alt+right"
        except Exception:
            pass

    if ch != "\x1b":
        return ch

    try:
        ch2 = stdscr.get_wch()
    except curses.error:
        return ch

    if ch2 != "[":
        if isinstance(ch2, str) and (("a" <= ch2 <= "z") or ch2 == "\r" or ch2 == "\n"):
            if ch2 == "\r" or ch2 == "\n":
                return "alt+enter"
            return f"alt+{ch2}"
        if ch2 == curses.KEY_LEFT:
            return "alt+left"
        if ch2 == curses.KEY_RIGHT:
            return "alt+right"
        return ch2

    try:
        ch3 = stdscr.get_wch()
    except curses.error:
        return -1

    if ch3 == "I":
        return KEY_FOCUS_IN
    elif ch3 == "O":
        return KEY_FOCUS_OUT
    elif ch3 == "A":
        return curses.KEY_UP
    elif ch3 == "B":
        return curses.KEY_DOWN
    elif ch3 == "C":
        return curses.KEY_RIGHT
    elif ch3 == "D":
        return curses.KEY_LEFT
    elif ch3 == "H":
        return curses.KEY_HOME
    elif ch3 == "F":
        return curses.KEY_END
    elif ch3 in ("1", "3", "5", "6"):
        try:
            ch4 = stdscr.get_wch()
        except curses.error:
            return -1

        if ch4 == "~":
            if ch3 == "1":
                return curses.KEY_HOME
            elif ch3 == "3":
                return curses.KEY_DC
            elif ch3 == "5":
                return curses.KEY_PPAGE
            else:
                return curses.KEY_NPAGE
        elif ch3 == "1" and ch4 == ";":
            try:
                ch5 = stdscr.get_wch()  # Modifier
                ch6 = stdscr.get_wch()  # Direction
                if ch5 == "5":  # Ctrl
                    if ch6 == "D":
                        return "ctrl+left"
                    elif ch6 == "C":
                        return "ctrl+right"
                elif ch5 == "3":  # Alt
                    if ch6 == "D":
                        return "alt+left"
                    elif ch6 == "C":
                        return "alt+right"
                return -1
            except curses.error:
                return -1
        elif ch3 == "5" and ch4 == "D":
            return "ctrl+left"
        elif ch3 == "5" and ch4 == "C":
            return "ctrl+right"
        elif ch3 == "3" and ch4 == "D":
            return "alt+left"
        elif ch3 == "3" and ch4 == "C":
            return "alt+right"
        else:
            return -1
    else:
        return -1


def _addstr(stdscr, *args) -> bool:
    try:
        stdscr.addstr(*args)
    except curses.error:
        # Tolerate "addwstr() returned ERR" when drawing the character at the bottom right corner.
        pass
    except ValueError:
        # If an invalid character is passed, simply stop rendering, for example, an "embedded null character".
        return False

    return True


class _Command:
    def __init__(
        self, hotkey: Optional[str], func: Callable, name: Optional[str] = None
    ):
        self.hotkey = hotkey
        self.func = func
        if name is not None:
            self.name = name
        else:
            self.name = func.__name__.strip("_")

    def __str__(self) -> str:
        if self.hotkey is not None:
            return "[%s] %s" % (get_hotkey_abbr(self.hotkey), self.name)
        else:
            return self.name


def _match_fuzzy(item: Any, patt: str) -> bool:
    patt = patt.lower()
    if not patt:
        return True
    else:
        return all([(x in str(item).lower()) for x in patt.split(" ")])


def _match_regex(item: Any, patt: str) -> bool:
    if not patt:
        return True
    else:
        try:
            return re.search(patt, str(item), re.IGNORECASE) is not None
        except re.error:
            return False


def _match(item: Any, patt: str, fuzzy_match: bool, index: int) -> bool:
    if patt[:1] == ":" and patt[1:].isdigit():
        return int(patt) == index + 1
    elif fuzzy_match:
        return _match_fuzzy(item, patt)
    else:
        return _match_regex(item, patt)


def _to_curses_color(color: Union[str, int]) -> int:
    if isinstance(color, int):
        if color >= curses.COLORS:
            return -1
        return color
    has_256 = curses.COLORS >= 256
    return {
        "black": curses.COLOR_BLACK,
        "red": curses.COLOR_RED,
        "green": curses.COLOR_GREEN,
        "yellow": curses.COLOR_YELLOW,
        "blue": curses.COLOR_BLUE,
        "magenta": curses.COLOR_MAGENTA,
        "cyan": curses.COLOR_CYAN,
        "white": -1,
        "gray": curses.COLOR_WHITE,
        "darkgray": 240 if has_256 else curses.COLOR_BLACK,
        "brightblack": 8 if has_256 else curses.COLOR_BLACK,
        "darkblue": 17 if has_256 else curses.COLOR_BLUE,
    }.get(color.lower(), -1)


def _get_ansi_color(code: int) -> int:
    return [
        curses.COLOR_BLACK,
        curses.COLOR_RED,
        curses.COLOR_GREEN,
        curses.COLOR_YELLOW,
        curses.COLOR_BLUE,
        curses.COLOR_MAGENTA,
        curses.COLOR_CYAN,
        curses.COLOR_WHITE,
    ][code - 30]


class _TextInput:
    def __init__(
        self,
        prompt="",
        prompt_color="white",
        text="",
        ascii_only=False,
        auto_complete=False,
    ):
        self.prompt = prompt
        self.prompt_color = prompt_color
        self.text = text
        self.set_text(text)
        self.ascii_only = ascii_only
        self.auto_complete = auto_complete

    def set_text(self, text):
        self.text = text
        self.caret_pos = len(text)

    class DrawInputResult(NamedTuple):
        cursor_x: int
        cursor_y: int
        last_x: int
        last_y: int

    def draw_input(self, stdscr, row, show_enter_symbol=False) -> DrawInputResult:
        """_summary_

        Args:
            stdscr (_type_): _description_
            row (_type_): _description_

        Returns:
            int: The index of the last row of text being drawn on the screen.
        """

        assert Menu._stdscr is not None

        # Draw label
        _addstr(
            stdscr,
            row,
            0,
            self.prompt,
            Menu._get_color_pair(self.prompt_color),
        )

        y, x = Menu._stdscr.getyx()  # type: ignore
        _addstr(stdscr, y, x, " ")  # Add a space between label and text input
        y, x = Menu._stdscr.getyx()  # type: ignore

        # Draw text before caret with dark gray background
        attr = Menu._get_color_pair("white", "darkgray")
        _addstr(stdscr, y, x, self.text[: self.caret_pos], attr)
        cursor_y, cursor_x = Menu._stdscr.getyx()  # type: ignore

        s = self.text[self.caret_pos :]
        if show_enter_symbol:
            s += " [↵]"

        # Draw text after caret with dark gray background
        _addstr(stdscr, cursor_y, cursor_x, s, attr)
        last_y, last_x = Menu._stdscr.getyx()  # type: ignore

        return _TextInput.DrawInputResult(
            cursor_x=cursor_x, cursor_y=cursor_y, last_x=last_x, last_y=last_y
        )

    def clear(self):
        self.text = ""
        self.caret_pos = 0

    def _move_word_backward(self):
        s = self.text
        i = self.caret_pos
        while i > 0 and not (s[i - 1].isalnum() or s[i - 1] == "_"):
            i -= 1
        while i > 0 and (s[i - 1].isalnum() or s[i - 1] == "_"):
            i -= 1
        self.caret_pos = i

    def _move_word_forward(self):
        s = self.text
        i = self.caret_pos
        while i < len(s) and not (s[i].isalnum() or s[i] == "_"):
            i += 1
        while i < len(s) and (s[i].isalnum() or s[i] == "_"):
            i += 1
        self.caret_pos = i

    def on_char(self, ch):
        if ch == curses.ERR:
            pass
        elif ch == curses.KEY_LEFT or ch == 452:  # curses.KEY_B1
            self.caret_pos = max(self.caret_pos - 1, 0)
        elif ch == curses.KEY_RIGHT or ch == 454:  # curses.KEY_B3
            self.caret_pos = min(self.caret_pos + 1, len(self.text))
        elif ch in ("ctrl+left", "alt+left"):
            self._move_word_backward()
        elif ch in ("ctrl+right", "alt+right"):
            self._move_word_forward()
        elif _is_backspace_key(ch):
            if self.caret_pos > 0:
                if self.auto_complete:
                    self.text = self.text[: self.caret_pos - 1]
                else:
                    self.text = (
                        self.text[: self.caret_pos - 1] + self.text[self.caret_pos :]
                    )
                self.caret_pos = max(self.caret_pos - 1, 0)

        elif ch == curses.ascii.ctrl("u"):
            self.clear()
        elif ch == curses.ascii.ctrl("w"):
            position_after_last_space = max(0, self.text.rstrip().rfind(" ") + 1)
            self.text = self.text[:position_after_last_space]
            self.caret_pos = len(self.text)
        elif ch == curses.ascii.ctrl("a"):
            self.caret_pos = 0
        # HACK: Workaround for single and double quote on Windows
        elif ch == 530 and sys.platform == "win32":
            self._on_char("'")
        elif ch == 460 and sys.platform == "win32":
            self._on_char('"')
        elif isinstance(ch, str):
            self._on_char(ch)

    def _on_char(self, ch: str):
        if not self.ascii_only or (self.ascii_only and re.match("[\x00-\x7f]", ch)):
            self.insert_text(ch)

    def insert_text(self, text: str):
        if self.auto_complete:
            self.text = self.text[: self.caret_pos] + text
        else:
            self.text = self.text[: self.caret_pos] + text + self.text[self.caret_pos :]
        self.caret_pos += len(text)


T = TypeVar("T")
R = TypeVar("R")


class Menu(Generic[T]):
    _should_update_screen = False
    _color_pair_map: Dict[Tuple[int, int], int] = {}

    # Logging
    log_handler: Optional[logging.handlers.QueueHandler] = None
    logger: Optional[logging.Logger] = None
    original_handlers: Optional[List[logging.Handler]] = None
    original_level: Optional[int] = None

    _stdscr = None

    def __init__(
        self,
        allow_input=True,
        ascii_only=False,
        cancellable=True,
        close_on_selection=True,
        debug=False,
        history: Optional[str] = None,
        items: Optional[List[T]] = None,
        prompt="",
        text: Optional[str] = None,
        on_item_selected: Optional[Callable[[T], None]] = None,
        highlight: Optional[Union[OrderedDict[str, str], Dict[str, str]]] = None,
        fuzzy_search=True,
        enable_command_palette=True,
        search_on_enter=False,
        selected_index=0,
        wrap_text=False,
        search_mode=True,
        line_number=True,
        prompt_color="white",
        follow=False,
        auto_complete=False,
    ):
        self.close_on_selection: bool = close_on_selection
        self.is_cancelled: bool = False
        self.items: List[T] = items if items is not None else []
        self.last_key_pressed_timestamp: float = 0.0

        self._height: int = -1

        self.__input = _TextInput(
            prompt=prompt,
            text=text if text else "",
            ascii_only=ascii_only,
            prompt_color=prompt_color,
            auto_complete=auto_complete,
        )

        self.__last_key: Union[int, str] = -1
        self.__allow_input: bool = allow_input
        self.__cancellable: bool = cancellable
        self.__closed: bool = False
        self.__debug = debug
        self.__empty_lines: int = 0

        self.__highlight = highlight
        self.__is_stdscr_owner: Optional[bool] = None
        self.__last_input: Optional[str] = None
        self.__last_item_count = 0
        self.__last_selected_item: Optional[T] = None
        self.__line_number = line_number
        self.__matched_item_indices: List[int] = []
        self.__message: Optional[str] = None
        self.__num_rendered_items: int = 0
        self.__on_item_selected = on_item_selected
        self.__search_history: List[str] = []
        self.__width: int = -1
        self.__wrap_text: bool = wrap_text

        # Search
        self.__search_mode = search_mode
        self.__search_on_enter: bool = search_on_enter
        self.__fuzzy_search = fuzzy_search

        # Scroll
        self.__scroll_y: int = 0
        self.__scroll_x = 0
        self.__can_scroll = False

        # Selection
        self.__follow = follow
        self.__selected_row_begin: int = selected_index
        self.__selected_row_end: int = selected_index
        self.__multi_select_mode: bool = False
        self.__should_update_matched_items: bool = False
        self.__auto_complete = auto_complete

        # Avoid updating the matching items when input changes too often.
        self.__last_match_time: float = 0

        # Only update screen when _should_update_screen is True. This is set to True to
        # trigger the initial draw.
        self.__should_update_screen = True

        self.__event_queue: Queue[Callable[[], None]] = Queue()

        # History
        self.history = history
        if history:
            self.history_values = load_json(self.get_history_file(), [])
            sort_key = {val: i for i, val in enumerate(self.history_values)}
            sorted_items = sorted(
                zip(self.items, list(range(len(self.items)))),
                key=lambda x: sort_key.get(str(x[0]), sys.maxsize),
            )
            self.items = [x[0] for x in sorted_items]
            self.indices = [x[1] for x in sorted_items]

        # Commands and hotkeys
        self.__hotkeys: Dict[str, _Command] = {}
        self.__custom_commands: List[_Command] = []
        if enable_command_palette:
            self.add_command(self.ask_ai, hotkey="alt+i")
            self.add_command(self.__command_palette, hotkey="ctrl+p")
            self.add_command(self.__edit_text_in_external_editor, hotkey="ctrl+e")
            self.add_command(self.__goto, hotkey="ctrl+g")
            self.add_command(self.__logs, hotkey="alt+l")
            self.add_command(self.__prev_search_history, hotkey="alt+u")
            self.add_command(self.__select_all)
            self.add_command(self.__toggle_multi_select, hotkey="ctrl+x")
            self.add_command(self.__toggle_wrap, hotkey="alt+z")
            self.add_command(self.paste, hotkey="ctrl+v")
            self.add_command(self.voice_input, hotkey="alt+v")
            self.add_command(self.voice_input, hotkey="space space")
            self.add_command(self.yank, hotkey="ctrl+y")

            for item in self.items:
                if hasattr(item, "hotkey"):
                    hotkey = item.__dict__["hotkey"]
                    if hotkey:
                        self.add_command(
                            lambda item=item: self.__on_item_hotkey(item),
                            hotkey=hotkey,
                        )

    def __goto(self):
        selected = self.get_selected_item()
        if selected:
            from ext.contextmenu import ContextMenu

            ContextMenu(param=str(selected)).exec()

    def __logs(self):
        _logging_menu.exec()

    @staticmethod
    def __setup_logging():
        Menu.log_handler = logging.handlers.QueueHandler(_logging_menu.queue)
        Menu.logger = logging.getLogger()
        Menu.original_level = Menu.logger.level
        Menu.logger.setLevel(logging.DEBUG)
        Menu.original_handlers = list(Menu.logger.handlers)
        for handler in Menu.original_handlers:
            Menu.logger.removeHandler(handler)
        Menu.logger.addHandler(Menu.log_handler)

    @staticmethod
    def __teardown_logging():
        if Menu.logger:
            if Menu.log_handler:
                Menu.logger.removeHandler(Menu.log_handler)
                Menu.log_handler.close()
            if Menu.original_handlers is not None:
                for handler in Menu.original_handlers:
                    Menu.logger.addHandler(handler)
                Menu.original_handlers = None
            if Menu.original_level is not None:
                Menu.logger.setLevel(Menu.original_level)
                Menu.original_level = None

    def __enter__(self):
        if self.__is_stdscr_owner:
            raise Exception("Using with-clause on Menu object twice is not allowed")
        self.__is_stdscr_owner = Menu._stdscr is None
        if self.__is_stdscr_owner:
            Menu.__setup_logging()
            Menu.init_curses()

    def __exit__(self, exc_type, exc_val, traceback):
        if self.__is_stdscr_owner:
            Menu.destroy_curses()
            Menu.__teardown_logging()
        else:
            Menu._should_update_screen = True
        self.__is_stdscr_owner = False
        self.on_close()

    def voice_input(self):
        from utils.menu.exceptionmenu import ExceptionMenu
        from utils.menu.recordmenu import RecordMenu
        from utils.menu.speechtotextmenu import SpeechToTextMenu

        record_menu = RecordMenu()
        try:
            record_menu.exec()
        except NotImplementedError:
            self.set_message("Error: voice input not implemented")
            return

        out_file = record_menu.get_output_file()
        if not out_file:
            return

        try:

            def process_stt():
                stt_menu = SpeechToTextMenu(out_file)
                stt_menu.exec()
                text = stt_menu.get_result()
                if text:
                    self.insert_text(text)
                    if not record_menu.space_pressed:
                        self.on_enter_pressed()

            ExceptionMenu.retry(process_stt)
        finally:
            if os.path.exists(out_file):
                os.remove(out_file)

    def __select_all(self):
        self.set_selection(0, -1)

    def __prev_search_history(self):
        if len(self.__search_history) > 0:
            last_input = self.__search_history.pop(0)
            self.set_message(last_input)
            self.set_input(last_input, save_search_history=False)

    def yank(self):
        set_clip(self.__get_selected_lines())
        self.set_message("copied")

    def paste(self) -> bool:
        text = get_clip()
        if not text:
            return False
        self.insert_text(text)
        self.update_screen()
        return True

    def add_command(
        self, func: Callable, hotkey: Optional[str] = None, name: Optional[str] = None
    ) -> _Command:
        command = _Command(hotkey=hotkey, func=func, name=name)
        self.__custom_commands.append(command)

        if hotkey is not None:
            self.__hotkeys[hotkey] = command

        return command

    def delete_commands_if(self, condition: Callable[[_Command], bool]):
        for cmd in self.__custom_commands[:]:  # Iterate over a copy of the list
            if condition(cmd):
                self.__custom_commands.remove(cmd)

    def get_history_file(self):
        from utils.script.path import get_data_dir

        return os.path.join(get_data_dir(), "%s_history.json" % slugify(self.history))

    def match_item(self, patt: str, item: T, index: int) -> int:
        """
        Checks if an item matches a pattern.

        Args:
            patt (str): Pattern to match.
            item (T): Item to be checked.
            index (int): Item index.

        Returns:
            int: rank: greater than 0 if the item matches the pattern, 0 otherwise. Results will be ordered by rank from high to low.
        """

        s = str(item)
        return 1 if _match(s, patt, fuzzy_match=self.__fuzzy_search, index=index) else 0

    def get_item_indices(self):
        if self.__search_mode:
            return self.__matched_item_indices
        else:
            return range(len(self.items))

    def append_item(self, item: T):
        self.items.append(item)
        self.__last_item_count = len(self.items)
        added_index = self.__last_item_count - 1

        # Scroll to bottom if last line is selected
        if self.__search_mode:
            if self.match_item(self.__input.text, item, added_index):
                self.__matched_item_indices.append(added_index)

        self.update_screen()

    def clear_items(self):
        self.items.clear()
        self.__last_item_count = 0
        self.__matched_item_indices.clear()
        self.reset_selection()
        self.update_screen()

    def set_follow(self, follow: bool) -> None:
        self.__follow = follow

    def set_input(self, text: str, save_search_history=True):
        self.__input.set_text(text)
        if self.__search_mode:
            self.search_by_input(save_search_history=save_search_history)
        self.update_screen()

    def insert_text(self, text: str):
        self.__input.insert_text(text)
        self.update_screen()

    def get_input(self) -> str:
        return self.__input.text

    def set_prompt(self, prompt: str):
        self.__input.prompt = prompt
        self.update_screen()

    def clear_input(self, reset_selection=False) -> bool:
        if self.__input.text == "":
            return False

        if self.__search_mode:
            if reset_selection:
                self.set_input("")
                self.reset_selection()
            elif self.__selected_row_end >= 0 and self.__selected_row_end < len(
                self.__matched_item_indices
            ):  # select the same item when filter is removed
                row_number = self.__matched_item_indices[self.__selected_row_end]
                self.set_input("")
                self.set_selected_row(row_number)
            else:
                self.set_input("")
        else:
            self.set_input("")
        return True

    @staticmethod
    def run_raw(func: Callable[[], R]) -> R:
        if Menu._stdscr is None:
            return func()

        Menu.destroy_curses()
        try:
            return func()
        finally:
            Menu.init_curses()

    def exec(self) -> int:
        with self:
            self._exec()

        idx = self.get_selected_index()
        if self.history is not None and idx >= 0:
            try:
                self.history_values.remove(str(self.items[idx]))
            except ValueError:
                pass
            self.history_values.insert(0, str(self.items[idx]))
            save_json(self.get_history_file(), self.history_values)
            idx = self.indices[idx]

        return idx

    @staticmethod
    def _setup_focus_keys():
        try:
            if hasattr(curses, "define_key"):
                logging.debug("Using curses.define_key for focus events")
                curses.define_key("\x1b[I", KEY_FOCUS_IN)
                curses.define_key("\x1b[O", KEY_FOCUS_OUT)
            else:
                import ctypes

                logging.debug(
                    "curses.define_key not found, attempting to load ncurses via ctypes"
                )
                ncurses = None
                for libname in [
                    "libncursesw.so.6",
                    "libncursesw.so",
                    "libncurses.so.6",
                    "libncurses.so",
                ]:
                    try:
                        ncurses = ctypes.cdll.LoadLibrary(libname)
                        logging.debug(f"Loaded {libname}")
                        break
                    except Exception:
                        continue
                if ncurses:
                    ncurses.define_key.argtypes = [ctypes.c_char_p, ctypes.c_int]
                    ncurses.define_key.restype = ctypes.c_int
                    ncurses.define_key(b"\x1b[I", KEY_FOCUS_IN)
                    ncurses.define_key(b"\x1b[O", KEY_FOCUS_OUT)
                    logging.debug("Defined focus keys via ctypes ncurses")
                else:
                    logging.warning(
                        "Could not find ncurses library for focus key definition"
                    )
        except Exception as e:
            logging.error(f"Failed to setup focus keys: {e}")

    @staticmethod
    def init_curses():
        if Menu._stdscr is not None:
            return

        # Remove escape key delay for Linux system
        # See also: ESCDELAY in https://linux.die.net/man/3/ncurses
        os.environ.setdefault("ESCDELAY", "25")

        stdscr = curses.initscr()

        if EXPERIMENTAL_EANBLE_WINDOWS_VT and sys.platform == "win32":
            enable_windows_vt()
        sys.stdout.write("\x1b[?1004h")
        sys.stdout.flush()

        curses.noecho()
        # Enter raw mode. In raw mode, normal line buffering and processing of
        # interrupt, quit, suspend, and flow control keys are turned off. This
        # allows for the use of the hotkey Ctrl-S, which used to be associated
        # with XOFF/XON flow control. Ctrl-S functions as the XOFF command.
        curses.raw()
        curses.cbreak()
        curses.start_color()
        curses.use_default_colors()  # The default color is assigned to -1

        # Enable handling of special keys and parse escape sequences (e.g. arrow keys)
        stdscr.keypad(True)

        Menu._setup_focus_keys()

        stdscr.nodelay(False)
        stdscr.timeout(1000)
        Menu._stdscr = stdscr
        Menu._should_update_screen = True

    @staticmethod
    def _get_color_pair(fg: Union[int, str], bg: Union[int, str] = -1) -> int:
        fg_int = _to_curses_color(fg)
        bg_int = _to_curses_color(bg)
        if (fg_int, bg_int) not in Menu._color_pair_map:
            pair_index = len(Menu._color_pair_map) + 1
            curses.init_pair(pair_index, fg_int, bg_int)
            Menu._color_pair_map[(fg_int, bg_int)] = pair_index
        return curses.color_pair(Menu._color_pair_map[(fg_int, bg_int)])

    @staticmethod
    def destroy_curses():
        if Menu._stdscr is None:
            return
        curses.endwin()
        Menu._stdscr = None
        Menu._color_pair_map.clear()

        # Disable focus reporting
        sys.stdout.write("\x1b[?1004l")
        sys.stdout.flush()

    def _update_screen(self):
        assert Menu._stdscr is not None

        self._height, self.__width = Menu._stdscr.getmaxyx()  # type: ignore

        if sys.platform == "win32":
            Menu._stdscr.clear()
        else:
            # Use erase instead of clear to prevent flickering
            Menu._stdscr.erase()
        self.__on_update_screen(item_y_max=self._height - 1)
        Menu._stdscr.refresh()

    def reset_selection(self):
        self.set_selection(0, 0)

    def set_selected_row(self, selected_row: int):
        self.set_selection(selected_row, selected_row)

    def set_selected_item(self, item: T):
        def try_select_item(item: T) -> bool:
            for i, idx in enumerate(self.get_item_indices()):
                if self.items[idx] == item:
                    self.set_selected_row(i)
                    return True
            return False

        if not try_select_item(item):
            self.clear_input()
            try_select_item(item)

    def set_selection(self, begin_row: int, end_row: int):
        self.__update_matched_items()
        total = len(self.get_item_indices())

        if end_row == -1:
            end_row = total - 1

        if (
            begin_row == self.__selected_row_begin
            and end_row == self.__selected_row_end
        ):
            return

        if begin_row != end_row:
            self.__multi_select_mode = True
        self.__selected_row_begin = begin_row
        self.__selected_row_end = end_row

        if self.__selected_row_begin >= total:
            self.__selected_row_begin = max(0, total - 1)
        if self.__selected_row_end >= total:
            self.__selected_row_end = max(0, total - 1)
        self.__follow = self.__selected_row_end == total - 1
        self._check_if_item_selection_changed()
        self.update_screen()

    def __update_input_from_selection(self, index: int):
        if not self.__auto_complete:
            return

        item_indices = self.get_item_indices()
        assert 0 <= index < len(item_indices)
        item = self.items[item_indices[index]]
        self.__input.set_text(self.get_item_text(item))
        self.__last_input = self.__input.text

    def refresh(self):
        self.__update_matched_items(force_update=True)

    def __set_selection_by_offset(self, offset: int, multi_select: bool):
        total_rows = len(self.get_item_indices())
        if total_rows > 0:
            selected_row_end = min(
                max(self.__selected_row_end + offset, 0), total_rows - 1
            )
            selected_row_begin = (
                self.__selected_row_begin if multi_select else selected_row_end
            )
            self.set_selection(selected_row_begin, selected_row_end)
            if selected_row_begin == selected_row_end:
                self.__update_input_from_selection(selected_row_end)

    def on_keyboard_interrupt(self):
        sys.exit(0)

    # Returns True if we should exit main loop for the current window
    def process_events(
        self, timeout_sec: float = 0.0, raise_keyboard_interrupt=False
    ) -> bool:
        assert Menu._stdscr is not None

        if self.__closed:
            return True

        if timeout_sec > 0.0:
            Menu._stdscr.timeout(int(timeout_sec * 1000.0))
        else:
            Menu._stdscr.timeout(0)

        self.__update_matched_items()

        # Update screen
        if self.__should_update_screen or Menu._should_update_screen:
            Menu._should_update_screen = False
            self.__should_update_screen = False
            self._update_screen()

        # Keyboard event
        ch: Union[int, str] = -1
        try:
            ch = Menu._stdscr.get_wch()
        except curses.error:
            pass
        except KeyboardInterrupt:
            if raise_keyboard_interrupt:
                raise
            else:
                self.on_keyboard_interrupt()

        if ch != -1:  # getch() will return -1 when timeout
            ch = _decode_escape_sequence(Menu._stdscr, ch)
            if self.__debug:
                if isinstance(ch, str):
                    self.set_message(f"key={repr(ch)}")
                elif isinstance(ch, int):
                    self.set_message(f"key=0x{ch:x}")

            now = time.time()
            prev_timestamp = self.last_key_pressed_timestamp
            self.last_key_pressed_timestamp = now
            is_paste = (
                self.__allow_input
                and prev_timestamp > 0
                and (now - prev_timestamp) < PASTE_THRESHOLD_SEC
            )

            if ch == "alt+enter" and "alt+enter" not in self.__hotkeys:
                self.__input.on_char("\n")
                self.update_screen()

            elif self._check_alt_hotkey_win(ch):
                pass

            elif self.on_char(ch):
                self.update_screen()

            elif ch == KEY_FOCUS_IN:
                self.on_focus_gained()

            elif ch == KEY_FOCUS_OUT:
                self.on_focus_lost()

            elif ch == curses.ascii.ctrl("c"):
                if raise_keyboard_interrupt:
                    raise KeyboardInterrupt
                else:
                    self.on_keyboard_interrupt()

            elif ch == "@" and "@" in self.__hotkeys:
                self.__hotkeys["@"].func()

            elif (
                ch == " "
                and self.__last_key == " "
                and self.__input.text == " "
                and "space space" in self.__hotkeys
            ):
                if (
                    self.__allow_input
                    and self.__input.caret_pos > 0
                    and self.__input.text[self.__input.caret_pos - 1] == " "
                ):
                    self.__input.on_char(curses.KEY_BACKSPACE)
                self.__hotkeys["space space"].func()
                self.update_screen()
                ch = -1

            elif ch == " " and self.__input.text == "" and "space" in self.__hotkeys:
                self.__hotkeys["space"].func()

            elif ch in ("\n", "\r"):
                if is_paste:
                    self.__input.on_char("\n")
                    self._drain_paste(Menu._stdscr)
                    self.update_screen()
                else:
                    self.on_enter_pressed()

            elif ch in (curses.KEY_UP, KEY_A2, SHIFT_UP):
                self.__set_selection_by_offset(
                    offset=-1, multi_select=self.__multi_select_mode or ch == SHIFT_UP
                )

            elif ch in (curses.KEY_DOWN, KEY_C2, SHIFT_DOWN):
                self.__set_selection_by_offset(
                    offset=1, multi_select=self.__multi_select_mode or ch == SHIFT_DOWN
                )

            elif (
                ch in (curses.KEY_LEFT, 452) and "left" in self.__hotkeys
            ):  # curses.KEY_B3
                self.__hotkeys["left"].func()

            elif ch in (curses.KEY_LEFT, 452) and self.__can_scroll:  # curses.KEY_B1
                self.__scroll_x = max(self.__scroll_x - self.get_scroll_distance(), 0)
                self.update_screen()

            elif (
                ch in (curses.KEY_RIGHT, 454) and "right" in self.__hotkeys
            ):  # curses.KEY_B3
                self.__hotkeys["right"].func()

            elif ch in (curses.KEY_RIGHT, 454) and self.__can_scroll:  # curses.KEY_B3
                self.__scroll_x += self.get_scroll_distance()
                self.update_screen()

            elif ch in (curses.KEY_PPAGE, 451):  # curses.KEY_A3
                self.__set_selection_by_offset(
                    offset=-self.get_items_per_page(),
                    multi_select=self.__multi_select_mode,
                )

            elif ch in (curses.KEY_NPAGE, 457):  # curses.KEY_C3
                self.__set_selection_by_offset(
                    offset=self.get_items_per_page(),
                    multi_select=self.__multi_select_mode,
                )

            elif ch == curses.KEY_HOME or ch == 449:
                if len(self.get_item_indices()) > 0:
                    begin = (
                        0 if not self.__multi_select_mode else self.__selected_row_begin
                    )
                    end = 0
                    self.set_selection(begin, end)
                    if begin == end:
                        self.__update_input_from_selection(end)

            elif ch == curses.KEY_END or ch == 455:
                if len(self.get_item_indices()) > 0:
                    end = len(self.get_item_indices()) - 1
                    begin = (
                        end
                        if not self.__multi_select_mode
                        else self.__selected_row_begin
                    )
                    self.set_selection(begin, end)
                    if begin == end:
                        self.__update_input_from_selection(end)

            elif ch == curses.KEY_DC and "delete" in self.__hotkeys:
                self.__hotkeys["delete"].func()

            elif self._check_ctrl_hotkey(ch):
                pass

            elif self._check_shift_hotkey(ch):
                pass

            elif (
                sys.platform == "win32"
                and ch == 0x211
                and "alt+enter" in self.__hotkeys
            ):
                self.__hotkeys["alt+enter"].func()

            elif ch == "\x1b":  # escape key
                self.on_escape_pressed()

            elif ch != "\0":
                if self.__allow_input:
                    self.__input.on_char(ch)
                    self.update_screen()

            self.__last_key = ch

        if ch == -1 and timeout_sec > 0.0:  # getch() is timed-out
            self._on_idle()

        if self.__closed:
            self.on_exit()
            return True
        else:
            return False

    def _drain_paste(self, stdscr):
        """Read remaining pasted characters until a pause indicates paste is done."""
        while True:
            stdscr.timeout(int(PASTE_THRESHOLD_SEC * 1000))
            try:
                ch = stdscr.get_wch()
            except curses.error:
                break
            self.last_key_pressed_timestamp = time.time()
            if ch in ("\n", "\r"):
                self.__input.on_char("\n")
            elif _is_backspace_key(ch) or (
                isinstance(ch, str) and len(ch) == 1 and ch >= " "
            ):
                self.__input.on_char(ch)
            elif ch == -1:
                break

    def post_event(self, func: Callable[[], None]) -> None:
        self.__event_queue.put(func)

    def __update_matched_items(self, save_search_history=True, force_update=False):
        if self.__search_mode:
            if (
                force_update
                or self.__should_update_matched_items
                or (
                    time.time() > self.__last_match_time + PROCESS_EVENT_INTERVAL_SEC
                    and (
                        (
                            not self.__search_on_enter
                            and self.__last_input != self.__input.text
                        )
                        or self.__last_item_count != len(self.items)
                    )
                )
                or (len(self.items) < self.__last_item_count)
            ):
                matches: List[Tuple[int, int]] = []  # list of tuple of index and rank
                patt = (
                    self.__input.text[: self.__input.caret_pos]
                    if self.__auto_complete
                    else self.__input.text
                )
                for i, item in enumerate(self.items):
                    rank = self.match_item(patt, item, i)
                    if rank > 0:  # match
                        matches.append((i, rank))
                # Sort matches by rank in descending order, preserving order for equal ranks
                matches = sorted(matches, key=lambda x: x[1], reverse=True)
                self.__matched_item_indices[:] = [index for index, _ in matches]

                if self.__last_input != self.__input.text:
                    self.__selected_row_begin = 0
                    self.__selected_row_end = 0
                    self.__follow = False

                    # Auto complete
                    if (
                        self.__auto_complete
                        and self.__input.text
                        and len(self.__matched_item_indices) > 0
                    ):
                        matched_item = str(self.items[self.__matched_item_indices[0]])
                        patt = self.__input.text[: self.__input.caret_pos]
                        if matched_item.lower().startswith(patt.lower()):
                            # If the matched item starts with the current input, autocomplete it and keep the caret position
                            self.__input.text = (
                                patt + matched_item[self.__input.caret_pos :]
                            )
                        # Avoid recursive update
                        self.__last_input = self.__input.text
                else:
                    total = len(self.__matched_item_indices)
                    self.__selected_row_begin = clamp(
                        self.__selected_row_begin, 0, total - 1
                    )
                    self.__selected_row_end = clamp(
                        self.__selected_row_end, 0, total - 1
                    )

                self._check_if_item_selection_changed()

                if save_search_history and self.__last_input is not None:
                    self.__search_history.insert(0, self.__last_input)
                self.__last_input = self.__input.text
                self.__last_item_count = len(self.items)
                self.__last_match_time = time.time()
                self.__should_update_matched_items = False
                self.__should_update_screen = True

                self.on_matched_items_updated()

    def on_escape_pressed(self):
        if "escape" in self.__hotkeys:
            logging.debug("Hotkey pressed: escape")
            self.__hotkeys["escape"].func()
            return True
        else:
            if self.__cancellable:
                self.cancel()
            else:
                self.__input.clear()
                self.update_screen()

    def on_matched_items_updated(self):
        pass

    def _check_ctrl_hotkey(self, ch: Union[str, int]) -> bool:
        if isinstance(ch, str) and len(ch) > 1:
            return False

        if curses.ascii.isctrl(ch):
            char = curses.ascii.unctrl(ch)[-1].lower()
            htks = ["ctrl+" + char]
            if char == "@":
                htks.append("ctrl+space")

            for htk in htks:
                if htk in self.__hotkeys:
                    logging.debug(f"Hotkey pressed: {htk}")
                    self.__hotkeys[htk].func()
                    return True
        return False

    def _check_shift_hotkey(self, ch: Union[str, int]) -> bool:
        if isinstance(ch, str):
            if ch in self.__hotkeys:
                self.__hotkeys[ch].func()
                return True
            elif len(ch) == 1 and ch.isupper():
                htk = "shift+" + ch.lower()
                if htk in self.__hotkeys:
                    logging.debug(f"Hotkey pressed: {htk}")
                    self.__hotkeys[htk].func()
                    return True
        return False

    def _check_alt_hotkey_win(self, ch: Union[int, str]) -> bool:
        if sys.platform == "win32" and isinstance(ch, int):
            if ch >= 0x1A1 and ch <= 0x1BA:
                htk = "alt+" + chr(ord("a") + (ch - 0x1A1))
                if htk in self.__hotkeys:
                    logging.debug(f"Hotkey pressed: {htk}")
                    self.__hotkeys[htk].func()
                return True

        return False

    def _on_idle(self):
        self.on_idle()

    def on_exit(self):
        pass

    def on_idle(self):
        pass

    def on_close(self):
        pass

    def _reset_state(self):
        self.is_cancelled = False
        self.__closed = False

    def _exec(self):
        self._reset_state()
        self.update_screen()
        self.on_created()
        self.on_main_loop()
        done = False
        while not done:
            has_event = False
            while not self.__event_queue.empty():
                has_event = True
                event = self.__event_queue.get()
                event()
            done = self.process_events(
                timeout_sec=0.0 if has_event else PROCESS_EVENT_INTERVAL_SEC
            )
            self.on_main_loop()
        self.on_close()

    def get_selected_index(self):
        if self.is_cancelled:
            return -1
        elif len(self.get_item_indices()) > 0:
            return self.get_item_indices()[self.__selected_row_end]
        else:
            return -1

    def get_text(self) -> Optional[str]:
        if self.is_cancelled:
            return None
        else:
            return self.get_input()

    def get_items_per_page(self):
        return self.__num_rendered_items + self.__empty_lines

    class DrawTextResult(NamedTuple):
        last_y: int
        can_scroll_left: bool
        can_scroll_right: bool

    def __draw_text(
        self,
        row: int,
        col: int,
        s: str,
        ymax: int,  # max y (exclusive).
        fg: int = -1,
        bg: int = -1,
        wrap_text=False,
        scroll_x=0,
        bold=False,
        dim=False,
        reverse=False,
    ) -> DrawTextResult:
        """_summary_

        Args:
            row (int): _description_
            col (int): _description_
            s (str): _description_

        Returns:
            int: The index of the last row of text being drawn on the screen.
        """
        assert Menu._stdscr is not None
        assert row >= 0
        assert col >= 0

        if row >= ymax:
            raise Exception(
                f'row should be smaller than ymax, but row={row} yamx={ymax} s="{s}"'
            )

        attr = Menu._get_color_pair(fg, bg)
        if bold:
            attr |= curses.A_BOLD
        if dim:
            attr |= curses.A_DIM
        if reverse:
            attr |= curses.A_REVERSE

        # Draw left arrow
        if scroll_x > 0:
            _addstr(
                Menu._stdscr,
                row,
                col,
                "<",
                attr ^ curses.A_REVERSE,
            )
            x = col + 1
        else:
            x = col

        last_row_index = y = row
        can_scroll_right = False

        visible_pos = 0
        i = 0
        while i < len(s):
            ch = s[i]

            # Handle ANSI color codes
            if ch == "\\" or ch == "\x1b":
                match = re.match(r"(?:\\x1b\[|\x1b\[)([0-9;]*)m", s[i:])
                if match:
                    i += match.end()
                    for code in match.group(1).split(";"):
                        if code in ("0", ""):
                            attr = curses.A_NORMAL
                            if bold:
                                attr |= curses.A_BOLD
                            if dim:
                                attr |= curses.A_DIM
                            if reverse:
                                attr |= curses.A_REVERSE
                        elif code == "1":
                            attr |= curses.A_BOLD
                        elif code == "2":
                            attr |= curses.A_DIM
                        elif code == "7":
                            if reverse:
                                attr &= ~curses.A_REVERSE
                            else:
                                attr |= curses.A_REVERSE
                        elif code == "22":
                            attr &= ~curses.A_BOLD
                            attr &= ~curses.A_DIM
                        elif code == "27":
                            if reverse:
                                attr |= curses.A_REVERSE
                            else:
                                attr &= ~curses.A_REVERSE
                        elif code.isdigit() and 30 <= int(code) <= 37:
                            attr = (attr & ~curses.A_COLOR) | Menu._get_color_pair(
                                _get_ansi_color(int(code))
                            )
                    continue

            # Skip visible chars
            if visible_pos < scroll_x:
                visible_pos += 1
                i += 1
                continue

            if not _addstr(Menu._stdscr, y, x, ch, attr):
                break

            last_y = y

            # Get current cursor position
            y, x = Menu._stdscr.getyx()  # type: ignore
            if wrap_text:
                if y >= ymax:
                    # If text overflows outside of the screen, set last_row_index to screen height.
                    last_row_index = ymax
                    break
                elif y > last_y:
                    x = col
            else:
                if y > last_y:
                    if i < len(s) - 1:
                        last_row_index = row
                        _addstr(
                            Menu._stdscr,
                            row,
                            self.__width - 1,
                            ">",
                            attr ^ curses.A_REVERSE,
                        )
                        can_scroll_right = True
                    break
            if x > col:
                last_row_index = y

            i += 1

        return Menu.DrawTextResult(
            last_y=last_row_index,
            can_scroll_left=scroll_x > 0,
            can_scroll_right=can_scroll_right,
        )

    def get_item_text(self, item: T) -> str:
        return str(item)

    def get_item_metadata(self, item: T) -> str:
        return self.get_item_text(item)

    def get_item_color(self, item: T) -> Union[str, Tuple[str, str]]:
        return "white"

    def goto_line(self, line: int):
        self.__scroll_y = line

    def item_wrap(self, item: T) -> bool:
        return self.__wrap_text

    def __on_update_screen(self, item_y_max: int):
        assert Menu._stdscr is not None

        # Render input widget
        draw_input_result = self.__input.draw_input(
            Menu._stdscr,
            0,
            show_enter_symbol=self.__should_trigger_search(),
        )

        # Get matched scripts
        item_y = draw_input_result.last_y + 1

        # Auto select last item
        item_indices = self.get_item_indices()
        total_items = len(item_indices)
        if self.__follow:
            if not self.__multi_select_mode:
                self.__selected_row_begin = total_items - 1
            self.__selected_row_end = total_items - 1
        else:
            self.__selected_row_begin = clamp(
                self.__selected_row_begin, 0, total_items - 1
            )
            self.__selected_row_end = clamp(self.__selected_row_end, 0, total_items - 1)

        # Draw status bar
        status_bar_text = self.get_status_text()
        lines = status_bar_text.splitlines()
        if len(lines) < self._height:
            for i, status_line in enumerate(lines):
                parts = status_line.split("\t", maxsplit=1)
                if len(parts) == 1:
                    status_line = parts[0]
                else:
                    status_bar_text, b = parts
                    left_width = max(0, self.__width - len(b))
                    status_line = (
                        f"{status_bar_text[:left_width]:<{left_width}}{b:>{len(b)}}"
                    )

                self.__draw_text(
                    row=self._height - len(lines) + i,
                    col=0,
                    s=status_line,
                    fg=-1,
                    ymax=self._height,
                )
            item_y_max -= len(lines) - 1

        # Update scroll y.
        items_per_page = self.get_items_per_page()
        if items_per_page > 0:
            if self.__selected_row_end >= self.__scroll_y + items_per_page:
                self.__scroll_y = _clamp(
                    self.__selected_row_end,
                    0,
                    len(item_indices) - items_per_page + 1,
                )
            elif self.__selected_row_end < self.__scroll_y:
                self.__scroll_y = _clamp(
                    self.__selected_row_end,
                    0,
                    len(item_indices) - items_per_page + 1,
                )

        self.__can_scroll = False
        matched_item_index = self.__scroll_y

        if self.__line_number and len(item_indices) > 0:
            line_number_width = len(self.get_line_number_text(item_indices[-1]))
        else:
            line_number_width = 0

        assert len(item_indices) <= len(self.items)
        while matched_item_index < len(item_indices) and item_y < item_y_max:
            item_index = item_indices[matched_item_index]
            self.__num_rendered_items = matched_item_index - self.__scroll_y + 1
            is_item_selected = (
                matched_item_index >= self.__selected_row_begin
                and matched_item_index <= self.__selected_row_end
            ) or (
                matched_item_index <= self.__selected_row_begin
                and matched_item_index >= self.__selected_row_end
            )
            item = self.items[item_index]
            item_text = self.get_item_text(self.items[item_index])

            # Item color
            item_color = self.get_item_color(item)
            if isinstance(item_color, tuple):
                fg_color, bg_color = item_color
            elif isinstance(item_color, str):
                fg_color, bg_color = item_color, -1
            else:
                raise ValueError(f"Invalid item color: {item_color}")
            fg: int = _to_curses_color(fg_color)
            bg: int = _to_curses_color(bg_color)

            # If a highlight is specified
            if self.__highlight is not None:
                for patt, c in self.__highlight.items():
                    if re.search(patt, item_text):
                        fg = _to_curses_color(c)

            # Draw item
            draw_text_result = self.__draw_text(
                item_y,
                line_number_width + (GUTTER_SIZE if self.__line_number else 0),
                item_text,
                wrap_text=self.item_wrap(item),
                fg=fg,
                bg=bg,
                reverse=is_item_selected,
                scroll_x=self.__scroll_x,
                ymax=item_y_max,
            )

            # Draw line number
            if self.__line_number:
                line_number_fg = _to_curses_color("brightblack")
                line_number_text = self.get_line_number_text(item_index)
                self.__draw_text(
                    item_y,
                    0,
                    line_number_text.rjust(line_number_width) + (" " * GUTTER_SIZE),
                    fg=line_number_fg,
                    reverse=is_item_selected,
                    ymax=item_y_max,
                )

                # Draw gutter
                for y in range(
                    item_y + 1, min(draw_text_result.last_y + 1, item_y_max - 1)
                ):
                    self.__draw_text(
                        y,
                        0,
                        " " * (line_number_width + GUTTER_SIZE),
                        fg=line_number_fg,
                        reverse=is_item_selected,
                        ymax=item_y_max,
                    )

            increments = draw_text_result.last_y + 1 - item_y

            # Ensure the selected item text is fully visible on the screen.
            if (
                self.__selected_row_end == matched_item_index
                and item_y + increments >= item_y_max
            ):
                self.__scroll_y = max(self.__scroll_y - 1, 0)
                self.update_screen()

            if self.item_wrap(item):
                matched_item_index += 1
            else:
                matched_item_index += increments

            item_y += increments

            self.__empty_lines = max(0, item_y_max - draw_text_result.last_y - 1)

            if draw_text_result.can_scroll_left or draw_text_result.can_scroll_right:
                self.__can_scroll = True

        if items_per_page != self.get_items_per_page():
            self.update_screen()

        # Move cursor
        try:
            Menu._stdscr.move(draw_input_result.cursor_y, draw_input_result.cursor_x)
        except curses.error:
            pass

    def get_scroll_distance(self) -> int:
        return 10

    def get_status_text(self) -> str:
        status = ""
        if self.__message:
            status += self.__message
        status += "\t"
        item_indices = self.get_item_indices()
        if len(item_indices) > 0:
            current_position = self.__selected_row_end + 1
            total_items = len(item_indices)
            indicators = []
            if self.__multi_select_mode:
                indicators.append("MS")
            if self.__follow:
                indicators.append("F")
            indicators.append(f"{current_position}/{total_items}")
            status += " ".join(indicators)
        return status

    def get_selected_item(self, ignore_cancellation=False) -> Optional[T]:
        if not ignore_cancellation and self.is_cancelled:
            return None
        elif len(self.get_item_indices()) > 0:
            item_index = self.get_item_indices()[self.__selected_row_end]
            return self.items[item_index]
        else:
            return None

    def get_selected_row_range(self) -> Tuple[int, int]:
        i = self.__selected_row_begin
        j = self.__selected_row_end
        if i > j:
            i, j = j, i
        return i, j

    def get_selected_indices(self) -> Iterator[int]:
        if len(self.get_item_indices()) > 0:
            i = self.__selected_row_begin
            j = self.__selected_row_end
            if i > j:
                i, j = j, i
            for idx in self.get_item_indices()[i : j + 1]:
                yield idx
        else:
            return

    def get_selected_items(self) -> Iterator[T]:
        for item_index in self.get_selected_indices():
            yield self.items[item_index]

    def on_char(self, ch: Union[int, str]):
        if ch == "\t":
            return self.on_tab_pressed()

        elif isinstance(ch, str) and ch in self.__hotkeys:
            logging.debug(f"Hotkey pressed: {ch}")
            self.__hotkeys[ch].func()
            return True

        else:
            return False

    def __should_trigger_search(self) -> bool:
        if self.__search_mode:
            return self.__search_on_enter and self.__input.text != self.__last_input
        else:
            return False

    def search_by_input(self, save_search_history=True) -> bool:
        if self.__should_trigger_search():
            self.__update_matched_items(
                save_search_history=save_search_history, force_update=True
            )
            return True
        else:
            return False

    def on_enter_pressed(self):
        if self.search_by_input():
            return

        else:
            item = self.get_selected_item()
            if item is not None:
                self.on_item_selected(item)
            if self.close_on_selection:
                self.close()
            else:
                self.update_screen()

    def on_item_selected(self, item: T):
        on_item_selected = self.__on_item_selected
        if on_item_selected is not None:
            self.run_raw(lambda item=item: on_item_selected(item))

    def on_tab_pressed(self) -> bool:
        if "tab" in self.__hotkeys:
            self.__hotkeys["tab"].func()
            return True
        else:
            item = self.get_selected_item()
            if item is not None:
                self.set_input("%s" % item)
            return True

    def on_main_loop(self):
        pass

    def on_created(self):
        pass

    def close(self):
        self.__closed = True

    def is_closed(self):
        return self.__closed

    def cancel(self):
        self.is_cancelled = True
        self.__closed = True

    def _check_if_item_selection_changed(self):
        selected = None
        item_indices = self.get_item_indices()
        item_index = -1
        if self.__selected_row_end < len(item_indices):
            item_index = item_indices[self.__selected_row_end]
            if item_index < len(self.items):
                selected = self.items[item_index]

        if (
            selected != self.__last_selected_item
            or self.__last_input != self.__input.text
        ) and not _is_backspace_key(self.__last_key):
            self.on_item_selection_changed(selected, i=item_index)
            self.update_screen()
        self.__last_selected_item = selected

    def on_item_selection_changed(self, item: Optional[T], i: int):
        pass

    def on_focus_gained(self):
        pass

    def on_focus_lost(self):
        pass

    def set_message(self, message: Optional[str] = None):
        if message:
            self.__message = message
        else:
            message = None
        logging.info(f"set_message: {message}")
        self.update_screen()

    def __edit_text_in_external_editor(self):
        text = self.__input.text
        new_text = self.run_raw(lambda: edit_text(text))
        self.set_input(new_text)
        if new_text != text:
            self.on_enter_pressed()

    def __command_palette(self):
        menu = Menu(
            prompt="cmd",
            items=self.__custom_commands,
            enable_command_palette=False,
        )
        menu.exec()
        hotkey = menu.get_selected_item()
        if hotkey is not None:
            hotkey.func()
        self.update_screen()

    def update_screen(self):
        self.__should_update_screen = True

    def __toggle_multi_select(self):
        self.set_multi_select(not self.__multi_select_mode)

    def __toggle_wrap(self):
        self.__wrap_text = not self.__wrap_text
        self.update_screen()

    def set_multi_select(self, mode: bool):
        self.__multi_select_mode = mode
        if not self.__multi_select_mode:
            self.__selected_row_begin = self.__selected_row_end
        self.update_screen()

    def __on_item_hotkey(self, item: T):
        # Select the item.
        i = self.items.index(item)
        self.set_selection(i, i)

        if self.close_on_selection:
            self.close()
        else:
            self.update_screen()

    def get_row_count(self):
        return len(self.__matched_item_indices)

    def get_line_number_text(self, item_index: int) -> str:
        return f"{item_index + 1}"

    def __get_selected_lines(self) -> str:
        selected_items = self.get_selected_items()
        return "\n".join([str(x) for x in selected_items])

    def ask_ai(self, extra_args: Optional[List[str]] = None):
        selected_items = self.get_selected_items()
        if selected_items:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", encoding="utf-8", delete=False
            ) as f:
                f.write(
                    "\n".join(
                        [
                            "<selected>",
                            *(self.get_item_metadata(x) for x in selected_items),
                            "</selected>",
                        ]
                    )
                )
                tmpfile = f.name

            args = [
                "start_script",
                "r/ai/coder.py",
                "--context",
                tmpfile,
            ]
            if extra_args:
                args += extra_args

            self.run_raw(lambda: subprocess.run(args))


class LoggingMenu(Menu):
    def __init__(self):
        self.queue = Queue()
        super().__init__(prompt="logs")

    def on_idle(self):
        while not self.queue.empty():
            record = self.queue.get()
            for line in record.getMessage().splitlines():
                self.append_item(line)


_logging_menu = LoggingMenu()
