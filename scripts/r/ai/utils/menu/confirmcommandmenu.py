import json
import shlex
from fnmatch import fnmatch

from ai.utils.tools import Settings
from utils.editor import edit_text
from utils.menu.menu import Menu

# Operators that sequence independent commands. We split on these and require
# every sub-command to be allowed, so an allowed prefix can't carry an extra
# command (e.g. "git x; rm -rf ~").
_SPLIT_OPERATORS = {";", "&&", "||", "|"}

# Characters shlex groups into operator tokens. Any operator run other than the
# sequencing operators above (redirect, subshell, backgrounding, &>, |&, ...)
# can't be vetted by prefix matching, so the command is never auto-allowed.
_PUNCTUATION = set("();<>|&")
_SAFE_STDERR_REDIRECTS = ("2>/dev/null", "2>&1")
_INTRINSICALLY_ALLOWED_COMMANDS = {"true"}


def _strip_safe_stderr_redirects(command: str) -> str:
    """Remove harmless unquoted stderr redirects before allowlist matching."""
    chars = list(command)
    quote: str | None = None
    index = 0
    while index < len(command):
        char = command[index]
        if char == "\\" and quote != "'":
            index += 2
            continue
        if char in {"'", '"'}:
            if quote == char:
                quote = None
            elif quote is None:
                quote = char
            index += 1
            continue
        if quote is None and (
            index == 0
            or command[index - 1].isspace()
            or command[index - 1] in ";|&("
        ):
            for redirect in _SAFE_STDERR_REDIRECTS:
                end = index + len(redirect)
                if command.startswith(redirect, index) and (
                    end == len(command)
                    or command[end].isspace()
                    or command[end] in ";|&()<>"
                ):
                    chars[index:end] = " " * len(redirect)
                    index = end
                    break
            else:
                index += 1
            continue
        index += 1
    return "".join(chars)


def _parse_commands(command: str) -> tuple[list[list[str]] | None, str | None]:
    if "\n" in command or "\r" in command:
        return None, (
            "The command contains a newline, which may separate multiple shell "
            "commands and cannot be safely matched against the allowed patterns."
        )
    lex = shlex.shlex(
        _strip_safe_stderr_redirects(command),
        posix=True,
        punctuation_chars=True,
    )
    lex.whitespace_split = True
    lex.commenters = ""  # Do not discard a potentially executable remainder.
    try:
        tokens = list(lex)
    except ValueError as ex:
        if "No closing quotation" in str(ex):
            quote_type = "single" if lex.state == "'" else "double"
            return None, (
                f"The command contains an unterminated {quote_type}-quoted string "
                "and cannot be parsed. It would fail in the shell even if confirmed."
            )
        return None, f"The command could not be parsed as shell syntax: {ex}"

    commands: list[list[str]] = [[]]
    for tok in tokens:
        if tok in _SPLIT_OPERATORS:
            commands.append([])
        elif tok and all(ch in _PUNCTUATION for ch in tok):
            return None, (
                f"The command uses unsupported shell operator `{tok}`, which cannot "
                "be safely matched against the allowed patterns."
            )
        elif "$" in tok or "`" in tok:
            return None, (
                "The command uses shell expansion or command substitution, which "
                "cannot be safely matched against the allowed patterns."
            )
        else:
            commands[-1].append(tok)
    return commands, None


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


def get_command_confirmation_reason(
    command: str,
    allowed_commands: list[str],
    ignore_case: bool = False,
) -> str | None:
    commands, parse_error = _parse_commands(command.strip())
    if parse_error is not None:
        return parse_error
    if commands is None:
        raise RuntimeError("Command parsing failed without an error reason")

    parts = [" ".join(args) for args in commands if args]
    if not parts:
        return "The command is empty."

    unallowed = [
        part
        for part in parts
        if not _matches_allowed_command(part, allowed_commands, ignore_case)
    ]
    if not unallowed:
        return None
    if len(unallowed) == 1:
        return f"`{unallowed[0]}` does not match an allowed command pattern."
    formatted = ", ".join(f"`{part}`" for part in unallowed)
    return f"These commands do not match allowed command patterns: {formatted}."


class ConfirmCommandMenu(Menu[str]):
    def __init__(
        self,
        command: str,
        prompt: str = "run this command?",
        reason: str | None = None,
        **kwargs,
    ):
        self.command_base = command.split()[0] if command.strip() else ""
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
        if self.command_base:
            self.add_command(
                self.__save_and_confirm,
                hotkey="s",
                name=f"save `{self.command_base} *`",
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

        reason = get_command_confirmation_reason(
            command,
            allowed_commands,
            ignore_case,
        )
        if reason is None:
            return

        menu = ConfirmCommandMenu(
            command=command,
            prompt="run this command?",
            reason=reason,
        )
        menu.exec()
        if not menu.is_confirmed():
            raise KeyboardInterrupt("Command execution was canceled by the user")

        if menu.__save:
            pattern = f"{menu.command_base} *"
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
