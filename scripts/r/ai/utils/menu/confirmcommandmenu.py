import json
from dataclasses import dataclass
from enum import Enum, auto
from fnmatch import fnmatch

from ai.utils.tools import Settings
from utils.editor import edit_text
from utils.menu.menu import Menu

_SPLIT_OPERATORS = {";", "&&", "||", "|"}
_OPERATOR_CHARS = set("();<>|&")
_SAFE_STDERR_REDIRECTS = ("2>/dev/null", "2>&1")
_INTRINSICALLY_ALLOWED_COMMANDS = {"true"}


class _TokenKind(Enum):
    WORD = auto()
    OPERATOR = auto()


@dataclass(frozen=True)
class _ShellToken:
    kind: _TokenKind
    value: str
    start: int
    end: int


def _is_environment_assignment(token: str) -> bool:
    name, separator, _ = token.partition("=")
    return bool(
        separator
        and name
        and (name[0].isalpha() or name[0] == "_")
        and all(char.isalnum() or char == "_" for char in name[1:])
    )


def _strip_environment_assignments(args: list[str]) -> list[str]:
    index = 0
    while index < len(args) and _is_environment_assignment(args[index]):
        index += 1
    return args[index:]


def _lex_shell(command: str) -> tuple[list[_ShellToken] | None, str | None]:
    tokens: list[_ShellToken] = []
    word: list[str] = []
    word_started = False
    word_start = 0
    quote: str | None = None
    expansion_used = False
    index = 0

    def start_word(position: int):
        nonlocal word_started, word_start
        if not word_started:
            word_started = True
            word_start = position

    def emit_word(end: int):
        nonlocal word_started
        if word_started:
            tokens.append(_ShellToken(_TokenKind.WORD, "".join(word), word_start, end))
            word.clear()
            word_started = False

    while index < len(command):
        char = command[index]
        if quote == "'":
            if char == "'":
                quote = None
            else:
                word.append(char)
            start_word(index)
            index += 1
            continue
        if quote == '"':
            if char == '"':
                quote = None
            elif char == "\\" and index + 1 < len(command) and command[index + 1] in '$`"\\\n':
                index += 1
                if command[index] != "\n":
                    word.append(command[index])
            elif char in {"$", "`"}:
                expansion_used = True
                word.append(char)
            else:
                word.append(char)
            start_word(index)
            index += 1
            continue
        if char.isspace():
            emit_word(index)
            index += 1
            continue
        if char == "\\":
            start_word(index)
            if index + 1 >= len(command):
                return None, "Trailing backslash; the shell will reject it."
            index += 1
            if command[index] in "\n\r":
                return None, "Contains a newline, which may run multiple commands."
            word.append(command[index])
            index += 1
            continue
        if char in {"'", '"'}:
            start_word(index)
            quote = char
            index += 1
            continue
        if char in {"$", "`"}:
            expansion_used = True
            start_word(index)
            word.append(char)
            index += 1
            continue
        if char in _OPERATOR_CHARS:
            emit_word(index)
            end = index + 1
            while end < len(command) and command[end] in _OPERATOR_CHARS:
                end += 1
            tokens.append(_ShellToken(_TokenKind.OPERATOR, command[index:end], index, end))
            index = end
            continue
        start_word(index)
        word.append(char)
        index += 1

    if quote is not None:
        quote_type = "single" if quote == "'" else "double"
        return None, f"Unterminated {quote_type}-quoted string; the shell will reject it."
    if expansion_used:
        return None, "Uses shell expansion or command substitution; not allowlist-safe."
    emit_word(len(command))
    return tokens, None


def _parse_commands(command: str) -> tuple[list[list[str]] | None, str | None]:
    if "\n" in command or "\r" in command:
        return None, "Contains a newline, which may run multiple commands."
    tokens, lex_error = _lex_shell(command)
    if lex_error is not None:
        return None, lex_error
    if tokens is None:
        raise RuntimeError("Shell lexing failed without an error reason")

    commands: list[list[str]] = [[]]
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if (
            index + 2 < len(tokens)
            and token.kind is _TokenKind.WORD
            and tokens[index + 1].kind is _TokenKind.OPERATOR
            and tokens[index + 2].kind is _TokenKind.WORD
            and token.end == tokens[index + 1].start
            and tokens[index + 1].end == tokens[index + 2].start
        ):
            redirect = command[token.start : tokens[index + 2].end]
            if redirect in _SAFE_STDERR_REDIRECTS:
                index += 3
                continue
        if token.kind is _TokenKind.OPERATOR:
            if token.value in _SPLIT_OPERATORS:
                commands.append([])
                index += 1
                continue
            return None, f"Uses unsupported shell operator `{token.value}`; not allowlist-safe."
        commands[-1].append(token.value)
        index += 1

    return [_strip_environment_assignments(args) for args in commands], None


def _matches_allowed_command(
    command: str,
    allowed_commands: list[str],
    ignore_case: bool,
) -> bool:
    normalized_command = command.lower() if ignore_case else command
    if normalized_command in _INTRINSICALLY_ALLOWED_COMMANDS:
        return True
    return any(
        fnmatch(
            normalized_command,
            pattern.lower() if ignore_case else pattern,
        )
        for pattern in allowed_commands
    )


@dataclass(frozen=True)
class _CommandConfirmation:
    reason: str
    save_pattern: str | None = None


def _get_save_pattern(args: list[str]) -> str:
    return " ".join(args)


def _get_command_confirmation(
    command: str,
    allowed_commands: list[str],
    ignore_case: bool = False,
) -> _CommandConfirmation | None:
    commands, parse_error = _parse_commands(command.strip())
    if parse_error is not None:
        return _CommandConfirmation(reason=parse_error)
    if commands is None:
        raise RuntimeError("Command parsing failed without an error reason")

    parts = [(" ".join(args), args) for args in commands if args]
    if not parts:
        return _CommandConfirmation(
            reason="Empty command or environment assignments only."
        )

    unallowed = [
        (part, args)
        for part, args in parts
        if not _matches_allowed_command(part, allowed_commands, ignore_case)
    ]
    if not unallowed:
        return None

    save_pattern = _get_save_pattern(unallowed[0][1])
    if len(unallowed) == 1:
        reason = f"Not allowlisted: `{unallowed[0][0]}`"
    else:
        formatted = ", ".join(f"`{part}`" for part, _ in unallowed)
        reason = f"Not allowlisted: {formatted}"
    return _CommandConfirmation(reason=reason, save_pattern=save_pattern)


def get_command_confirmation_reason(
    command: str,
    allowed_commands: list[str],
    ignore_case: bool = False,
) -> str | None:
    confirmation = _get_command_confirmation(
        command,
        allowed_commands,
        ignore_case,
    )
    return confirmation.reason if confirmation else None


class ConfirmCommandMenu(Menu[str]):
    def __init__(
        self,
        command: str,
        prompt: str = "run this command?",
        reason: str | None = None,
        save_pattern: str | None = None,
        **kwargs,
    ):
        self.save_pattern = save_pattern
        if reason:
            prompt = f"{prompt} (reason: {reason})"
        super().__init__(
            items=command.splitlines() or [""],
            prompt=prompt,
            prompt_color="green",
            search_mode=False,
            line_number=False,
            wrap_text=True,
            **kwargs,
        )
        self.confirmed = False
        self.__save = False

        self.add_command(self.__confirm, hotkey="y", name="yes", pinned=True)
        self.add_command(self.__cancel, hotkey="n", name="no", pinned=True)
        if self.save_pattern:
            self.add_command(
                self.__save_and_confirm,
                hotkey="s",
                name="save",
                pinned=True,
            )

    def __confirm(self):
        self.confirmed = True
        self.close()

    def __cancel(self):
        self.confirmed = False
        self.close()

    def __save_and_confirm(self):
        self.confirmed = True
        self.__save = True
        self.close()

    def on_enter_pressed(self):
        self.__confirm()

    def is_confirmed(self):
        return self.confirmed

    @staticmethod
    def confirm_command(
        command: str,
        allowed_commands: list[str],
        save_path: str,
        ignore_case: bool = False,
    ):
        if not Settings.need_confirm:
            return

        confirmation = _get_command_confirmation(
            command,
            allowed_commands,
            ignore_case,
        )
        if confirmation is None:
            return

        menu = ConfirmCommandMenu(
            command=command,
            prompt="run this command?",
            reason=confirmation.reason,
            save_pattern=confirmation.save_pattern,
        )
        menu.exec()
        if not menu.is_confirmed():
            raise KeyboardInterrupt("Command execution was canceled by the user")

        if menu.__save:
            if menu.save_pattern is None:
                raise RuntimeError("Save requested without an allowlist pattern")
            pattern = menu.save_pattern
            if save_path:
                edited_pattern = menu.run_raw(lambda: edit_text(pattern)).strip()
                if edited_pattern:
                    pattern = edited_pattern
                else:
                    return

            if pattern not in allowed_commands:
                allowed_commands.append(pattern)
                allowed_commands.sort()

            if save_path:
                with open(save_path, "w") as f:
                    json.dump(allowed_commands, f, indent=4)
