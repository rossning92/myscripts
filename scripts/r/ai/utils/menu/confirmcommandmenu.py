import json
import shlex
from fnmatch import fnmatch

from ai.utils.tools import Settings
from utils.menu.menu import Menu

# Operators that sequence independent commands. We split on these and require
# every sub-command to be allowed, so an allowed prefix can't carry an extra
# command (e.g. "git x; rm -rf ~").
_SPLIT_OPERATORS = {";", "&&", "||", "|"}

# Characters shlex groups into operator tokens. Any operator run other than the
# sequencing operators above (redirect, subshell, backgrounding, &>, |&, ...)
# can't be vetted by prefix matching, so the command is never auto-allowed.
_PUNCTUATION = set("();<>|&")


def _split_commands(command: str) -> list[list[str]] | None:
    # Returns the sub-commands (each a list of args), or None when the command
    # uses shell features we won't auto-vet or can't be parsed.
    if "\n" in command or "\r" in command:
        # Newlines separate commands in shell but are plain whitespace to shlex,
        # which would merge them into one (mis-matched) command.
        return None
    lex = shlex.shlex(command, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    lex.commenters = ""  # never silently drop a '#...' remainder of the command
    try:
        tokens = list(lex)
    except ValueError:
        return None
    commands: list[list[str]] = [[]]
    for tok in tokens:
        if tok in _SPLIT_OPERATORS:
            commands.append([])
        elif tok and all(ch in _PUNCTUATION for ch in tok):
            return None
        elif "$" in tok or "`" in tok:
            return None
        else:
            commands[-1].append(tok)
    return commands


def is_command_allowed(
    command: str,
    allowed_commands: list[str],
    ignore_case: bool = False,
) -> bool:
    commands = _split_commands(command.strip())
    if commands is None:
        return False
    parts = [c for c in commands if c]
    if not parts:
        return False

    def matches(cmd: str) -> bool:
        return any(
            fnmatch(cmd.lower() if ignore_case else cmd, p.lower() if ignore_case else p)
            for p in allowed_commands
        )

    return all(matches(" ".join(args)) for args in parts)


class ConfirmCommandMenu(Menu[str]):
    def __init__(self, command: str, prompt: str = "Run this command?", **kwargs):
        self.command_base = command.split()[0] if command.strip() else ""
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
        self.__always = False
        self.__save = False

        self.add_command(self.__confirm, hotkey="y", name="yes", pinned=True)
        self.add_command(self.__cancel, hotkey="n", name="no", pinned=True)
        if self.command_base:
            self.add_command(
                self.__always_confirm,
                hotkey="a",
                name=f"allow `{self.command_base} *`",
                pinned=True,
            )
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

    def __always_confirm(self):
        self.confirmed = True
        self.__always = True
        self.close()

    def __save_and_confirm(self):
        self.confirmed = True
        self.__always = True
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
        prompt_prefix: str = "Run",
    ):
        if not Settings.need_confirm:
            return

        if is_command_allowed(command, allowed_commands, ignore_case):
            return

        menu = ConfirmCommandMenu(command=command, prompt=f"{prompt_prefix} this command?")
        menu.exec()
        if not menu.is_confirmed():
            raise KeyboardInterrupt("Command execution was canceled by the user")

        if menu.__always:
            pattern = f"{menu.command_base} *"
            if pattern not in allowed_commands:
                allowed_commands.append(pattern)
                allowed_commands.sort()

            if menu.__save and save_path:
                with open(save_path, "w") as f:
                    json.dump(allowed_commands, f, indent=4)
