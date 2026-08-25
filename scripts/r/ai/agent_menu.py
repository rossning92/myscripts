import functools
import glob
import os
import shlex
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypedDict, cast

import ai.chat_menu
import ai.utils.tools.bash
import ai.utils.tools.edit
import ai.utils.tools.grep
import ai.utils.tools.powershell
import ai.utils.tools.read
import ai.utils.tools.web_fetch
import ai.utils.tools.web_search
from ai.chat_menu import ChatMenu, Line
from ai.utils.mcp import MCPClient
from ai.utils.memory import get_memory_prompt
from ai.utils.menu.confirmcommandmenu import ConfirmCommandMenu
from ai.utils.message import Message
from ai.utils.skill import get_skill_prompt, get_skills
from ai.utils.tools.permission import ALLOWED_COMMANDS, ALLOWED_COMMANDS_FILE
from ai.utils.tooluse import (
    ToolDefinition,
    ToolParam,
    ToolResult,
    ToolUse,
    function_to_tool_definition,
)
from utils.jsonschema import JSONSchema
from utils.jsonutil import load_json
from utils.menu.confirmmenu import ConfirmMenu
from utils.menu.filemenu import FileMenu
from utils.menu.menu import PROCESS_EVENT_INTERVAL_SEC

MODULE_NAME = Path(__file__).stem
DATA_DIR = os.path.join(".config", MODULE_NAME)


def _get_prompt(
    skill: bool = False,
    memory: bool = False,
) -> str:
    prompt_parts = []

    if memory:
        memory_prompt = get_memory_prompt()
        if memory_prompt:
            prompt_parts.append(memory_prompt)

    if skill:
        skill_prompt = get_skill_prompt()
        if skill_prompt:
            prompt_parts.append(skill_prompt)

    return "\n\n".join(p.strip() for p in prompt_parts if p.strip())


class _MCP(TypedDict):
    command: str


class _Subagent(TypedDict):
    name: str
    description: str
    system_prompt: str


class SettingsMenu(ai.chat_menu.SettingsMenu):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_default_values(self) -> Dict[str, Any]:
        return {
            **super().get_default_values(),
            "enable_tools": True,
            "mcp": [],
            "skill": True,
            "memory": False,
            "subagent": False,
        }

    def get_schema(self) -> Optional[JSONSchema]:
        schema = super().get_schema()
        assert schema and schema["type"] == "object"
        schema["properties"]["enable_tools"] = {"type": "boolean"}
        schema["properties"]["mcp"] = {
            "type": "array",
            "items": {"type": "object", "properties": {"command": {"type": "string"}}},
        }
        schema["properties"]["skill"] = {"type": "boolean"}
        schema["properties"]["memory"] = {"type": "boolean"}
        schema["properties"]["subagent"] = {"type": "boolean"}
        return schema


def load_subagents() -> List[_Subagent]:
    script_dir = Path(__file__).parent
    subagents_dir = script_dir / "subagents"
    subagents: List[_Subagent] = []

    for json_file in glob.glob(str(subagents_dir / "*.json")):
        subagent: _Subagent = load_json(json_file)
        agent_name = Path(json_file).stem
        subagent["name"] = agent_name
        subagents.append(subagent)
    return subagents


class AgentMenu(ChatMenu):
    def __init__(
        self,
        yes_always=True,
        settings_menu_class=SettingsMenu,
        mcp: Optional[List[_MCP]] = None,
        subagents: Optional[List[_Subagent]] = None,
        tools_callable: Optional[List[Callable]] = None,
        **kwargs,
    ):
        self.__yes_always = yes_always
        self.__subagents = subagents if subagents else []

        super().__init__(
            settings_menu_class=settings_menu_class,
            **kwargs,
        )

        mcp_items = mcp if mcp else cast(List[_MCP], self.get_settings()["mcp"])
        self.__mcp_clients = [
            MCPClient(command=shlex.split(item["command"])) for item in mcp_items
        ]

        self.add_command(self.__open_file_menu, hotkey="alt+f")
        self.add_command(self.__toggle_tools, hotkey="ctrl+t")

        self.__tools_callable = (
            tools_callable
            if tools_callable is not None
            else [
                (
                    self.__hook_read_tool(ai.utils.tools.read.read)
                    if self.get_settings()["skill"]
                    else ai.utils.tools.read.read
                ),
                ai.utils.tools.edit.edit,
                (
                    ai.utils.tools.powershell.powershell
                    if sys.platform == "win32"
                    else ai.utils.tools.bash.bash
                ),
                ai.utils.tools.grep.grep,
                ai.utils.tools.web_fetch.web_fetch,
                ai.utils.tools.web_search.web_search,
            ]
        )

        self.__update_tools()

    def __update_tools(self):
        self.__tools = self.get_tools()

    def __get_tool_uses(self, message: Message) -> List[ToolUse]:
        return list(message.get("tool_use", []))

    def __run_blocking(self, func: Callable[[], Any]) -> Any:
        # Run a blocking tool call on a worker thread while pumping the curses
        # event loop on this (main) thread, so the UI stays responsive while we
        # wait. Mirrors how a nested menu.exec() loop keeps the parent live.
        result: Dict[str, Any] = {}
        done = threading.Event()

        def worker():
            try:
                result["value"] = func()
            except BaseException as ex:  # noqa: BLE001 - re-raised on main below.
                result["error"] = ex
            finally:
                done.set()

        threading.Thread(target=worker, daemon=True).start()

        while not done.is_set():
            if self.process_events(timeout_sec=PROCESS_EVENT_INTERVAL_SEC):
                break  # Menu was closed; stop pumping.

        if "error" in result:
            raise result["error"]
        return result.get("value")

    def __execute_tool(self, tool_use: ToolUse):
        tool_name = tool_use["tool_name"]
        tool = next(
            (t for t in self.get_tools_callable() if t.__name__ == tool_name),
            None,
        )
        if tool:
            if tool_name in ["bash", "powershell"]:
                ConfirmCommandMenu.confirm_command(
                    command=tool_use["args"]["command"],
                    allowed_commands=ALLOWED_COMMANDS,
                    save_path=str(ALLOWED_COMMANDS_FILE),
                )
                return self.__run_blocking(lambda: tool(**tool_use["args"]))
            return tool(**tool_use["args"])

        client = next(
            (
                c
                for c in self.__mcp_clients
                if any(t.name == tool_use["tool_name"] for t in c.list_tools())
            ),
            None,
        )
        if client:
            return client.call_tool(tool_use)

        subagent = next(a for a in self.__subagents if a["name"] == tool_name)
        menu = AgentMenu(
            system_prompt=subagent["system_prompt"],
            prompt=f"subagent={tool_name}",
            message=tool_use["args"]["prompt"],
            tools_callable=self.get_tools_callable(),
            yes_always=self.__yes_always,
            cancellable=True,
        )
        menu.exec()
        return menu.get_messages()[-1]["text"]

    def __confirm_tool_use(self, tool_use: ToolUse) -> bool:
        if self.__yes_always:
            return True
        menu = ConfirmMenu(f"Run tool ({tool_use['tool_name']})?")
        menu.exec()
        return menu.is_confirmed()

    def on_message(self, content: str):
        self.__handle_response()

    def on_enter_pressed(self):
        if self._is_agent_running():
            super().on_enter_pressed()
            return

        if not self.get_input() and not self._out_message:
            messages = self.get_messages()
            if messages and messages[-1]["role"] == "assistant":
                last_message = messages[-1]
                tool_uses = self.__get_tool_uses(last_message)
                if tool_uses:
                    self.__handle_response()
                    return
        super().on_enter_pressed()

    def __get_tools_subagent(self) -> List[ToolDefinition]:
        if not self.get_settings().get("subagent", False):
            return []
        subagents = self.__subagents
        return [
            ToolDefinition(
                name=subagent["name"],
                description=subagent["description"],
                parameters=[
                    ToolParam(
                        name="prompt",
                        type={"type": "string"},
                        description="The task for the agent to perform",
                    ),
                ],
                required=["prompt"],
            )
            for subagent in subagents
        ]

    def get_tools_callable(self) -> List[Callable]:
        return self.__tools_callable

    def get_tools(self) -> List[ToolDefinition]:
        if not self.get_settings()["enable_tools"]:
            return []

        return (
            [function_to_tool_definition(t) for t in self.get_tools_callable()]
            + self.__get_tools_subagent()
            + [t for client in self.__mcp_clients for t in client.list_tools()]
        )

    def get_system_prompt(self) -> str:
        return _get_prompt(
            skill=self.get_settings()["skill"] and self.get_settings()["enable_tools"],
            memory=self.get_settings().get("memory", False),
        )

    def __handle_response(self):
        messages = self.get_messages()
        if len(messages) <= 0:
            return

        last_message = messages[-1]
        text_content = last_message["text"]

        interrupted = False
        has_error = False

        tool_uses = self.__get_tool_uses(last_message)

        tool_results: List[ToolResult] = []
        for tool_use in tool_uses:
            if not self.__confirm_tool_use(tool_use):
                tool_results.append(
                    ToolResult(
                        tool_use_id=tool_use["tool_use_id"],
                        content="Tool was interrupted by user",
                    )
                )
                break

            try:
                ret = self.__execute_tool(tool_use)

                if ret:
                    ret_str = str(ret)
                    tool_result = ToolResult(
                        tool_use_id=tool_use["tool_use_id"],
                        content=ret_str,
                    )
                    if ret_str.startswith("data:image/"):
                        tool_result["image_urls"] = [ret_str]
                        tool_result["content"] = "Image content returned."
                    tool_results.append(tool_result)
                else:
                    tool_results.append(
                        ToolResult(
                            tool_use_id=tool_use["tool_use_id"],
                            content="Tool completed",
                        )
                    )

            except Exception as ex:
                has_error = True
                tool_results.append(
                    ToolResult(
                        tool_use_id=tool_use["tool_use_id"],
                        content=str(ex),
                    )
                )
            except KeyboardInterrupt:
                interrupted = True
                tool_results.append(
                    ToolResult(
                        tool_use_id=tool_use["tool_use_id"],
                        content="Tool was interrupted by user",
                    )
                )
                break

        self.on_response(text_content, done=not tool_results)

        if tool_results:
            if not has_error and interrupted:
                self.append_user_message("", tool_results=tool_results)
            else:
                self.send_message("", tool_results=tool_results)

    def on_response(self, text: str, done: bool):
        pass

    def on_tool_use_start(self, tool_use: ToolUse):
        msg_index, subindex = self.get_message_index_and_subindex()
        self.append_item(
            Line(
                role="assistant",
                msg_index=msg_index,
                subindex=subindex,
                tool_use=tool_use,
            )
        )
        self.process_events()

    def on_tool_use_args_delta(self, text: str):
        pass

    def on_tool_use(self, tool_use: ToolUse):
        # Add or update tool use result
        exists = False
        for line in reversed(self.items):
            if (
                line.tool_use
                and line.tool_use["tool_use_id"] == tool_use["tool_use_id"]
            ):
                line.tool_use = tool_use
                exists = True
                break
        if not exists:
            msg_index, subindex = self.get_message_index_and_subindex()
            self.append_item(
                Line(
                    role="assistant",
                    msg_index=msg_index,
                    subindex=subindex,
                    tool_use=tool_use,
                )
            )

    def __toggle_tools(self):
        enabled = not self.get_settings()["enable_tools"]
        self.set_setting("enable_tools", enabled)
        self.__update_tools()
        self.set_message(f"Tools {'on' if enabled else 'off'}")

    def __open_file_menu(self):
        FileMenu(goto=os.getcwd()).exec()

    def get_status_text(self) -> str:
        s = f"cwd={os.getcwd()}"

        return s + "\n" + super().get_status_text()

    def on_close(self):
        for c in self.__mcp_clients:
            c.close()
        super().on_close()

    def __hook_read_tool(self, func):
        @functools.wraps(func)
        def wrapper(file: str, **kwargs) -> str:
            if skill := next((s for s in get_skills() if s.file_path == file), None):
                if mcp_servers := skill.metadata.get("mcp_servers"):
                    self.__mcp_clients.extend(
                        MCPClient(command=shlex.split(c)) for c in mcp_servers
                    )

                if allow := skill.metadata.get("allow"):
                    if isinstance(allow, str):
                        allow = [allow]
                    for cmd in allow:
                        if cmd not in ALLOWED_COMMANDS:
                            ALLOWED_COMMANDS.append(cmd)

                self.__update_tools()
                return skill.content
            return func(file=file, **kwargs)

        return wrapper


def _main():
    menu = AgentMenu(data_dir=DATA_DIR)
    menu.exec()


if __name__ == "__main__":
    _main()
