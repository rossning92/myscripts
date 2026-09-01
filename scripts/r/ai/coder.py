import argparse
import difflib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import ai.agent_menu
import ai.utils.tools.bash
import ai.utils.tools.powershell
from ai.agent_menu import AgentMenu, load_subagents
from ai.chat_menu import Line
from ai.utils.env import get_env_info
from ai.utils.filecontextmenu import FileContextMenu
from ai.utils.rules import get_project_rule_file, get_rules_prompt
from ai.utils.tools import Settings
from ai.utils.tooluse import ToolUse
from utils.editor import edit_text_file
from utils.menu.filemenu import FileMenu
from utils.notify import send_notify

_DIFF_CONTEXT_LINES = 0
_DEFAULT_MODEL = "gpt-5.6-sol"

_SYSTEM_PROMPT = (
    (Path(__file__).parent / "coder.system.md").read_text(encoding="utf-8").strip()
)


class SettingsMenu(ai.agent_menu.SettingsMenu):
    default_model = _DEFAULT_MODEL

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__update_settings()

    def get_default_values(self) -> Dict[str, Any]:
        return {
            **super().get_default_values(),
            "model": SettingsMenu.default_model,
            "need_confirm": True,
        }

    def on_dict_update(self, data):
        super().on_dict_update(data)
        self.__update_settings()

    def __update_settings(self):
        Settings.need_confirm = self.data["need_confirm"]


class CoderMenu(AgentMenu):
    def __init__(
        self,
        files: Optional[List[str]] = None,
        voice_input: bool = False,
        settings_menu_class=SettingsMenu,
        extra_system_prompt: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            data_dir=os.path.join(".config", "coder"),
            settings_menu_class=settings_menu_class,
            subagents=load_subagents(),
            title="coder",
            **kwargs,
        )
        self.__file_context_menu = FileContextMenu(files=files)
        self.__extra_system_prompt = extra_system_prompt
        self.__voice_input_enabled = voice_input
        self.add_command(self.__add_file, hotkey="alt+a")
        self.add_command(self.__edit_project_rule)

    def on_created(self):
        super().on_created()
        if self.__voice_input_enabled:
            self.voice_input()

    def __edit_project_rule(self):
        file = get_project_rule_file(self.get_data_dir(), "AGENTS.md")
        self.run_raw(lambda: edit_text_file(str(file)))

    def get_system_prompt(self) -> str:
        prompt_parts = []

        rules = get_rules_prompt(self.get_data_dir())
        if rules:
            prompt_parts.append(rules)

        prompt_parts.append(_SYSTEM_PROMPT)

        system = super().get_system_prompt()
        if system:
            prompt_parts.append(system)

        if self.__extra_system_prompt:
            prompt_parts.append(self.__extra_system_prompt)

        file_context = self.__file_context_menu.get_prompt()
        if file_context:
            prompt_parts.append(file_context)

        env = get_env_info()
        if env:
            prompt_parts.append(env)

        return "\n\n".join(p.strip() for p in prompt_parts if p.strip())

    def get_status_text(self) -> str:
        status_lines = []
        files = self.__file_context_menu.get_status_text()
        if files:
            status_lines.append(files)
        status_lines.append(super().get_status_text())
        return "\n".join(status_lines)

    def __add_file(self):
        file_menu = FileMenu()
        file = file_menu.select_file()
        if file:
            cwd = os.getcwd()
            if os.path.commonpath([cwd, file]) == cwd:
                path = os.path.relpath(file, cwd)
            else:
                path = file
            self.insert_text(f"`{path}` ")

    def _get_tool_use_lines(
        self, tool_use: ToolUse, msg_index: int, subindex: int
    ) -> List[Line]:
        lines = super()._get_tool_use_lines(tool_use, msg_index, subindex)
        if tool_use["tool_name"] == "edit":
            lines.extend(
                self.__get_edit_diff_lines(tool_use, msg_index, subindex + len(lines))
            )
        return lines

    def on_tool_use(self, tool_use: ToolUse):
        super().on_tool_use(tool_use)
        if tool_use["tool_name"] == "edit":
            msg_index, subindex = self.get_message_index_and_subindex()
            for line in self.__get_edit_diff_lines(tool_use, msg_index, subindex):
                self.append_item(line)

    def on_generating(self):
        send_notify(app="coder", hint="running")

    def __get_edit_diff_lines(
        self, tool_use: ToolUse, msg_index: int, subindex: int
    ) -> List[Line]:
        old_string = tool_use["args"].get("old_string", "")
        new_string = tool_use["args"].get("new_string", "")

        class IgnoreLeadingWhitespaceLine(str):
            def __eq__(self, other):
                return self.lstrip() == other.lstrip()

            def __hash__(self):
                return hash(self.lstrip())

        diff = difflib.unified_diff(
            [IgnoreLeadingWhitespaceLine(line) for line in old_string.splitlines()],
            [IgnoreLeadingWhitespaceLine(line) for line in new_string.splitlines()],
            n=_DIFF_CONTEXT_LINES,
            lineterm="",
        )
        lines = []
        for line in diff:
            if line.startswith(("---", "+++", "@@")):
                continue
            lines.append(
                Line(
                    role="assistant",
                    text=line,
                    msg_index=msg_index,
                    subindex=subindex,
                    type="diff",
                )
            )
            subindex += 1
        return lines

    def get_item_color(self, item: Line) -> Union[str, Tuple[str, str]]:
        if item.type == "diff":
            if item.text.startswith("+"):
                return "green"
            elif item.text.startswith("-"):
                return "red"
        return super().get_item_color(item)

    def item_wrap(self, item: Line) -> bool:
        if item.type == "diff":
            return False
        return super().item_wrap(item)


def _find_git_root(path) -> Optional[str]:
    current = Path(path)
    while current != current.parent:
        if (current / ".git").exists():
            return str(current)
        current = current.parent
    return None


def _main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*")
    parser.add_argument(
        "-d",
        "--repo-path",
        "--dir",
        dest="repo_path",
        type=str,
        default=os.environ.get("REPO_PATH"),
    )
    parser.add_argument(
        "-c",
        "--context",
        type=str,
        nargs="?",
        help="context file path or context text",
    )
    parser.add_argument("--system-prompt", type=str, help="extra system prompt")
    parser.add_argument("-p", "--prompt", type=str, help="initial user prompt")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="print the response without showing the menu (requires --prompt)",
    )
    parser.add_argument("-m", "--model", type=str)
    parser.add_argument("--allow", action="append", help="allow certain bash commands")
    parser.add_argument("--voice-input", action="store_true")
    args = parser.parse_args()

    if args.headless and args.prompt is None:
        parser.error("--headless requires --prompt")

    if args.model:
        SettingsMenu.default_model = args.model

    if args.allow:
        ai.utils.tools.bash.ALLOWED_COMMANDS.extend(args.allow)
        ai.utils.tools.powershell.ALLOWED_COMMANDS.extend(args.allow)

    # Change directory to the project root
    if len(args.files) == 1 and os.path.isabs(args.files[0]):
        root = os.path.dirname(args.files[0])
        git_root = _find_git_root(root)
        if git_root:
            root = git_root
    elif args.repo_path:
        if not os.path.exists(args.repo_path):
            os.makedirs(args.repo_path, exist_ok=True)
        root = args.repo_path
    else:
        git_root = _find_git_root(os.getcwd())
        if git_root:
            root = git_root
        else:
            root = os.getcwd()
    os.chdir(root)

    # Convert files to relative path
    files = [
        os.path.relpath(file, root) if os.path.isabs(file) else file
        for file in args.files
    ]

    system_prompt = args.system_prompt
    if system_prompt and os.path.isfile(system_prompt):
        with open(system_prompt, "r", encoding="utf-8") as f:
            system_prompt = f.read()

    menu = CoderMenu(
        files=files,
        context=args.context,
        extra_system_prompt=system_prompt,
        message=args.prompt,
        headless=args.headless,
        voice_input=args.voice_input,
    )
    menu.exec()


if __name__ == "__main__":
    _main()
