import argparse
import asyncio
import base64
import glob
import hashlib
import os
import subprocess
import sys
import tempfile
from concurrent.futures import Future
from datetime import datetime
from pathlib import Path
from pprint import pformat
from queue import Empty, Queue
from threading import Thread
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Union
from urllib.parse import unquote_to_bytes

from ai.chat import (
    complete_chat,
    get_context_text,
    get_image_url_text,
    get_reasoning_text,
    get_tool_result_text,
    get_tool_use_text,
)
from ai.models import DEFAULT_MODEL, MODEL_IDS, get_model
from ai.utils.llama_cpp_server import ensure_llama_cpp_server
from ai.utils.message import Message
from ai.utils.tooluse import ToolDefinition, ToolResult, ToolUse
from ai.utils.usagemetadata import UsageMetadata
from utils.clip import set_clip
from utils.dateutil import format_timestamp
from utils.editor import edit_text
from utils.encode_image_base64 import encode_image_base64
from utils.gitignore import create_gitignore
from utils.historymanager import HistoryManager
from utils.jsonschema import JSONSchema
from utils.jsonutil import load_json, save_json
from utils.menu import Menu
from utils.menu.exceptionmenu import ExceptionMenu
from utils.menu.filemenu import FileMenu
from utils.menu.inputmenu import InputMenu
from utils.menu.jsoneditmenu import JsonEditMenu
from utils.menu.listeditmenu import ListEditMenu
from utils.menu.textmenu import TextMenu
from utils.platform import is_termux
from utils.script.path import get_data_dir
from utils.shutil import shell_open
from utils.slugify import slugify
from utils.spinner import Spinner
from utils.template import render_template
from utils.term import set_terminal_title
from utils.textutil import is_text_file, truncate_text

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


_MODULE_NAME = Path(__file__).stem

_MAX_CHAT_HISTORY = 200

_INTERRUPT_MESSAGE = "[INTERRUPTED]"

EXPERIMENTAL_FOLLOW_NEW_MESSAGE = False

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


def _start_background_loop(loop: asyncio.AbstractEventLoop):
    """Run an asyncio loop forever in a background thread."""
    asyncio.set_event_loop(loop)
    loop.run_forever()


_loop = asyncio.new_event_loop()
Thread(target=_start_background_loop, args=(_loop,), daemon=True).start()


def _get_prompt_dir() -> str:
    prompt_dir = os.environ.get("PROMPT_DIR")
    if prompt_dir:
        return prompt_dir

    prompt_dir = os.path.join(_SCRIPT_DIR, "prompts")
    return prompt_dir


def get_default_data_dir():
    return os.path.join(get_data_dir(), _MODULE_NAME)


class SettingsMenu(JsonEditMenu):
    def __init__(self, json_file: str, model: Optional[str]) -> None:
        super().__init__(json_file=json_file)

        if model:
            self.data["model"] = model

    def get_default_values(self) -> Dict[str, Any]:
        return {"model": DEFAULT_MODEL, "retry": False}

    def get_schema(self) -> Optional[JSONSchema]:
        return {
            "type": "object",
            "properties": {
                "model": {"type": "string", "enum": MODEL_IDS},
                "retry": {"type": "boolean"},
            },
        }


class Line:
    def __init__(
        self,
        role: str,
        msg_index: int,
        subindex: int,
        text: str = "",
        image_url: Optional[str] = None,
        context: Optional[str] = None,
        reasoning: Optional[str] = None,
        tool_use: Optional[ToolUse] = None,
        tool_result: Optional[ToolResult] = None,
        type: Optional[str] = None,
    ) -> None:
        self.role = role
        self.text = text
        self.image_url = image_url
        self.context = context
        self.msg_index = msg_index
        self.subindex = subindex  # subindex with in the message
        self.reasoning = reasoning
        self.tool_use = tool_use
        self.tool_result = tool_result
        self.type = type

    def __str__(self) -> str:
        if self.context:
            return get_context_text(self.context)
        elif self.reasoning:
            return get_reasoning_text(self.reasoning)
        elif self.tool_use:
            return get_tool_use_text(self.tool_use)
        elif self.tool_result:
            return get_tool_result_text(self.tool_result)
        elif self.image_url:
            return get_image_url_text(self.image_url)
        else:
            return self.text


class _ChatItem:
    def __init__(
        self,
        path: str,
    ) -> None:
        self.path = path
        messages: List[Message] = load_json(path, default=[])

        file_name = os.path.splitext(os.path.basename(path))[0]
        display_name = "" if file_name.startswith("chat_") else file_name
        self.text = messages[0]["text"] if messages else ""
        ts = format_timestamp(os.path.getmtime(path))
        ts = f"\033[34m{ts}\033[0m" if ts else ts
        display_name = (
            f"\033[32m{display_name}\033[0m" if display_name else display_name
        )
        parts = [
            ts,
            display_name,
            truncate_text(self.text),
        ]
        self.preview = " ".join(part for part in parts if part)

    def __str__(self) -> str:
        return self.text


class _EditImageUrlsMenu(ListEditMenu):
    def __init__(self, items: List[str]) -> None:
        super().__init__(items=items, prompt="image urls")
        self.add_command(self.__insert_image, hotkey="alt+i")

    def __insert_image(self) -> None:
        menu = FileMenu()
        image_file = menu.select_file()
        if image_file:
            encoded = encode_image_base64(image_file)
            self.items.append(encoded)


class _SelectChatMenu(Menu[_ChatItem]):
    def __init__(self, chat_dir: str) -> None:
        self.__chat_dir = chat_dir
        super().__init__(prompt="load history chat")
        self.__refresh()
        self.add_command(self.__delete_chat, hotkey="ctrl+k")

    def __refresh(self):
        self.items[:] = [
            _ChatItem(f)
            for f in reversed(
                sorted(
                    glob.glob(os.path.join(self.__chat_dir, "*.json")),
                    key=os.path.getmtime,
                )
            )
        ]

    def __delete_chat(self):
        chats = self.get_selected_items()
        if chats and confirm("delete chat?"):
            for chat in chats:
                os.remove(chat.path)
            self.__refresh()

    def get_item_text(self, item: _ChatItem) -> str:
        return item.preview

    def match_item(self, patt: str, item: _ChatItem, index: int) -> int:
        return super().match_item(patt, item, index)


def _open_image(image_url: str):
    # Extract image data
    header, payload = image_url.split(",", 1)
    mime_type = header.split(";")[0].split(":", 1)[1]
    extension = mime_type.split("/")[1]
    data = (
        base64.b64decode(payload) if ";base64" in header else unquote_to_bytes(payload)
    )

    # Save image
    image_dir = os.path.join(get_default_data_dir(), "exported_images")
    os.makedirs(image_dir, exist_ok=True)
    hash_name = hashlib.md5(data).hexdigest()[:8]
    image_file = os.path.join(image_dir, f"{hash_name}.{extension}")
    if not os.path.exists(image_file):
        with open(image_file, "wb") as f:
            f.write(data)

    # Open image
    shell_open(image_file)


class ChatMenu(Menu[Line]):
    def __init__(
        self,
        copy=False,
        data_dir: Optional[str] = None,
        message: Optional[str] = None,
        model: Optional[str] = None,
        context: Optional[str] = None,
        image_urls: Optional[List[str]] = None,
        out_file: Optional[str] = None,
        prompt: str = "❯",
        prompt_file: Optional[str] = None,
        system_prompt="",
        settings_menu_class=SettingsMenu,
        settings_file: str = "settings.json",
        cancellable: bool = False,
        title: str = "chat_menu",
        **kwargs,
    ) -> None:
        self.__title = title
        self.__copy = copy
        self.__first_message = message
        if context and is_text_file(context):
            with open(context, "r", encoding="utf-8") as f:
                context = f.read()
        self.__context: Optional[str] = context
        self.__image_urls: List[str] = image_urls if image_urls else []
        self.__is_generating = False
        self.__spinner = Spinner()
        self.__last_copied_line: Optional[Line] = None
        self.__lines: List[Line] = []
        self.__prompt = prompt
        self.__prompt_file = prompt_file
        self.__out_file = out_file
        self.__system_prompt = system_prompt
        self.__copy_mode = 0
        self.__chat_task: Optional[Future[None]] = None
        self.__retry_count = 0
        self.__usage = UsageMetadata()
        self.__message_queue: List[str] = []

        self._out_message: Optional[Message] = None

        self.__data_dir = (
            data_dir if data_dir else os.path.join(".config", _MODULE_NAME)
        )
        os.makedirs(self.__data_dir, exist_ok=True)
        create_gitignore(self.__data_dir)

        self.__data_dir_menu = FileMenu(
            prompt="data dir", goto=self.__data_dir, sort_by="mtime", esc_to_close=True
        )
        self.__add_file_menu = FileMenu(
            prompt="add file", goto=self.__data_dir, sort_by="mtime"
        )

        self.__settings_menu = settings_menu_class(
            json_file=os.path.join(self.__data_dir, settings_file),
            model=model,
        )

        super().__init__(
            items=self.__lines,
            search_mode=False,
            wrap_text=True,
            line_number=True,
            follow=True,
            cancellable=cancellable,
            **kwargs,
        )

        self.add_command(self.__add_file, hotkey="alt+f")
        self.add_command(self.__edit_context)
        self.add_command(self.__edit_image_urls, hotkey="alt+i")
        self.add_command(self.__edit_message, hotkey="alt+e")
        self.add_command(self.__edit_prompt, hotkey="alt+p")
        self.add_command(self.__edit_settings, hotkey="alt+s")
        self.add_command(self.__go_prev_message, hotkey="left")
        self.add_command(self.__go_next_message, hotkey="right")
        self.add_command(self.__load_chat, hotkey="ctrl+l")
        self.add_command(self.__load_prompt, hotkey="tab")
        self.add_command(self.__save_prompt)
        self.add_command(self.__save_chat_as)
        self.add_command(self.__show_more, hotkey="tab")
        self.add_command(self.__take_photo)
        self.add_command(self.__show_system_prompt)
        self.add_command(self.__open_data_dir, hotkey="alt+d")
        self.add_command(self.__copy_messages, hotkey="ctrl+y", override=True)
        self.add_command(self.new_chat, hotkey="ctrl+n")
        self.add_command(self.save_chat, hotkey="ctrl+s")
        self.add_command(self.__revert_messages, hotkey="ctrl+z")

        self.__chat_dir = os.path.join(self.__data_dir, "conversations")
        self.__history_manager = HistoryManager(
            save_dir=self.__chat_dir,
            prefix="chat_",
            ext=".json",
            max_history=_MAX_CHAT_HISTORY,
        )

        self.__messages: List[Message] = []
        self.__chat_file = self.__history_manager.get_new_file()

        self.__update_terminal_title(state="idle")
        self.__update_prompt()

    def __add_file(self):
        file = self.__add_file_menu.select_file()
        if file:
            try:
                if _is_image_file(file):
                    self.__image_urls.append(encode_image_base64(file))
                else:
                    with open(file, "r", encoding="utf-8") as f:
                        self.__context = f.read()
            except (OSError, UnicodeError, ValueError) as e:
                self.set_message(f"failed to add file: {e}")
                return
            self.__update_prompt()

    def __copy_block(self, index: int):
        # Check if it's in the code block; if so, copy all the code.
        is_code_block = False
        start = -1
        stop = -1
        text: List[str] = []
        for i, line in enumerate(self.__lines):
            if line.text.startswith("```"):
                is_code_block = not is_code_block
                if is_code_block:
                    text.clear()
                    start = i + 1
                else:
                    stop = i - 1
                    if start <= index <= stop:
                        set_clip("\n".join(text))
                        self.set_selection(start, stop)
                        self.set_message("code copied")
                        return
            elif is_code_block:
                text.append(line.text)

        # Copy the whole message.
        msg_index = self.__lines[index].msg_index
        start = -1
        stop = -1
        text = []
        for i, line in enumerate(self.__lines):
            if line.msg_index == msg_index:
                if start == -1:
                    start = i
                stop = i
                text.append(line.text)
        set_clip("\n".join(text))
        self.set_selection(start, stop)
        self.set_message("message copied")
        return

    def __create_prompt_file_menu(self, prompt: str):
        return FileMenu(
            prompt=prompt,
            goto=_get_prompt_dir(),
            show_size=False,
            recursive=True,
            allow_cd=False,
            config_dir=os.path.join(".config", "load_prompt_menu"),
        )

    def __edit_context(self):
        if self.__context is None:
            self.__context = ""
        self.__context = self.run_raw(
            lambda: edit_text(self.__context, tmp_file_ext=".md")
        )
        if not self.__context.strip():
            self.__context = None
        self.__update_prompt()

    def __edit_image_urls(self):
        _EditImageUrlsMenu(items=self.__image_urls).exec()
        self.__update_prompt()

    def __edit_message(self, msg_index=-1):
        if msg_index < 0:
            selected = self.get_selected_item()
            if selected:
                msg_index = selected.msg_index
            else:
                self.set_message("error: no message selected")
                return

        if msg_index < 0 or msg_index >= len(self.get_messages()):
            self.set_message("error: no message to edit")
            return

        message = self.get_messages()[msg_index]
        content = message["text"]
        new_content = self.run_raw(lambda: edit_text(content, tmp_file_ext=".md"))
        if new_content != content:
            message["text"] = new_content

            # Delete all messages after.
            del self.get_messages()[msg_index + 1 :]

            self.__refresh_lines()
            self.__update_terminal_title()

            if message["role"] == "user":
                self.__complete_chat()

    def __edit_settings(self):
        self.__settings_menu.exec()

    def __navigate_message(self, direction: Literal["next", "prev"]):
        i = self.get_selected_index()
        if i < 0:
            return

        r = (
            range(i + 1, len(self.__lines))
            if direction == "next"
            else range(i - 1, -1, -1)
        )

        for j in r:
            line = self.__lines[j]
            if line.subindex == 0 and line.text:
                self.set_selected_item(line)
                return

    def __go_next_message(self):
        self.__navigate_message("next")

    def __go_prev_message(self):
        self.__navigate_message("prev")

    def __edit_prompt(self):
        self.__edit_message(msg_index=0)

    def __save_chat_as(self):
        menu = FileMenu(
            prompt="save chat as",
            goto=self.__chat_dir,
            show_size=False,
            allow_cd=False,
        )
        chat_file = menu.select_new_file(ext=".json")
        if not chat_file:
            return

        slugified_chat_file = slugify(chat_file)
        save_json(slugified_chat_file, self.__messages)
        self.__chat_file = slugified_chat_file
        self.set_message(f"chat saved to {slugified_chat_file}")

    def __save_prompt(self):
        line = self.get_selected_item()
        if not line:
            self.set_message("no message found")
            return

        message = self.get_messages()[line.msg_index]
        content = message["text"]

        menu = self.__create_prompt_file_menu(prompt="save prompt")
        prompt_file = menu.select_new_file(ext=".md")
        if not prompt_file:
            return

        os.makedirs(os.path.dirname(prompt_file), exist_ok=True)
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(content)

        self.set_message(f"prompt saved: {prompt_file}")

    def __load_chat(self):
        menu = _SelectChatMenu(chat_dir=self.__chat_dir)
        menu.exec()
        selected = menu.get_selected_item()
        if selected:
            self.load_chat(selected.path)

    def __load_prompt(self, prompt_file: Optional[str] = None):
        if not prompt_file:
            menu = self.__create_prompt_file_menu(prompt="load prompt")
            prompt_file = menu.select_file()

        if not prompt_file:
            return

        with open(prompt_file, "r", encoding="utf-8") as f:
            message = f.read()

        # Collect context values for template variables
        context: Dict[str, str] = {}
        while True:
            undefined_names: List[str] = []
            rendered_message = render_template(
                template=message,
                context=context,
                undefined_names=undefined_names,
            )
            if not undefined_names:
                break
            for name in undefined_names:
                val = InputMenu(prompt=f"enter {name}").request_input()
                if not val:
                    return
                context[name] = val

        self.set_input(self.get_input() + rendered_message)

    def __show_more(self) -> bool:
        selected = self.get_selected_item()
        if selected:
            if selected.reasoning:
                TextMenu(text=selected.reasoning, prompt="reasoning").exec()
                return True
            if selected.tool_result:
                tool_result_content = selected.tool_result["content"]
                TextMenu(text=tool_result_content, prompt="tool result").exec()
                return True
            elif selected.tool_use:
                args = pformat(selected.tool_use["args"], sort_dicts=False, width=200)
                TextMenu(text=args, prompt="tool use args").exec()
                return True
            elif selected.context:
                TextMenu(text=selected.context, prompt="context").exec()
                return True
            elif selected.image_url:
                _open_image(selected.image_url)
                return True
        return False

    def __take_photo(self):
        if not is_termux():
            self.set_message("taking photo is only supported on Android")
            return

        tmp_photo = os.path.join(tempfile.gettempdir(), "photo.jpg")
        try:
            subprocess.run(
                ["termux-camera-photo", "-c", "0", tmp_photo],
                check=True,
            )
        except Exception as e:
            self.set_message(f"failed to take photo: {e}")
            return

        # TODO: use self.__image_urls instead
        # self.__context = tmp_photo
        self.__update_prompt()

    def __revert_messages(self):
        selected = self.get_selected_item()
        if selected:
            self.revert_messages(from_msg_index=selected.msg_index)

    def revert_messages(self, from_msg_index: int) -> List[Message]:
        removed_messages: List[Message] = []
        messages = self.get_messages()

        if 0 <= from_msg_index < len(messages):
            removed_messages = messages[from_msg_index:]
            del messages[from_msg_index:]

        if not removed_messages:
            return []

        self.__message_queue.clear()

        self.__refresh_lines()
        oldest_removed = removed_messages[0]
        if oldest_removed["role"] == "user":
            self.set_input(oldest_removed["text"])
            self.__image_urls[:] = oldest_removed.get("image_urls", [])
            self.__context = oldest_removed.get("context")
        else:
            self.clear_input()

        self.__update_prompt()
        return removed_messages

    def __update_prompt(self):
        prompt = f"{self.__prompt}"
        if self.__context:
            prompt += " (context)"
        if self.__image_urls:
            prompt += f" ({len(self.__image_urls)} images)"
        if self.__message_queue:
            prompt += f" (queued: {len(self.__message_queue)})"
        self.set_prompt(prompt)

    def __update_terminal_title(
        self, state: Literal["idle", "generating", "done"] = "done"
    ):
        status = {"idle": "", "generating": "⧗", "done": "✓"}[state]
        title = self.__title + status
        if self.__messages:
            t = self.__messages[0].get("text", "")
            if t:
                title += " - " + t.splitlines()[0][:100]
        set_terminal_title(title)

    def __show_system_prompt(self):
        system_prompt = self.get_system_prompt()
        if system_prompt:
            TextMenu(text=system_prompt, prompt="system prompt").exec()
        else:
            self.set_message("no system prompt set")

    def __open_data_dir(self):
        self.__data_dir_menu.exec()

    def __copy_messages(self):
        indices = list(self.get_selected_indices())
        if len(indices) == 1:
            idx = indices[0]
            line = self.__lines[idx]
            if line != self.__last_copied_line:
                self.__copy_mode = 0
                self.__last_copied_line = line

            if self.__copy_mode == 0:
                set_clip(line.text)
                self.set_message(f"line {idx + 1} copied")
                self.__copy_mode = 1

            elif self.__copy_mode == 1:
                index = self.get_selected_index()
                if index >= 0:
                    self.__copy_block(index=index)
        elif len(indices) > 1:
            line_text = []
            for idx in indices:
                line = self.__lines[idx]
                line_text.append(line.text)
            set_clip("\n".join(line_text))
            self.set_message("selected line copied")
            self.set_multi_select(False)

    def get_data_dir(self):
        return self.__data_dir

    def get_message_index_and_subindex(self):
        num_messages = len(self.get_messages())
        msg_index = num_messages if self._out_message else num_messages - 1
        if len(self.items) > 0 and self.items[-1].msg_index == msg_index:
            subindex = self.items[-1].subindex + 1
        else:
            subindex = 0
        return msg_index, subindex

    def get_line_number_text(self, item_index: int) -> str:
        item = self.items[item_index]
        line_number_text = f"{item.msg_index + 1}"
        if item.subindex == 0:
            return line_number_text
        else:
            return " " * len(line_number_text)

    def get_item_color(self, item: Line) -> Union[str, Tuple[str, str]]:
        return "white" if item.role == "assistant" else ("white", "darkgray")

    def item_wrap(self, item: Line) -> bool:
        return super().item_wrap(item) if item.text else False

    def get_messages(self, expand_context=False) -> List[Message]:
        if expand_context:
            return [
                (
                    {
                        **message,
                        "text": message["text"]
                        + (
                            f"\n---\n{message['context']}"
                            if "context" in message
                            else ""
                        ),
                    }
                    if i == 0 and "context" in message
                    else message
                )
                for i, message in enumerate(self.__messages)
            ]
        else:
            return self.__messages

    def get_settings(self) -> Dict[str, Any]:
        return self.__settings_menu.data

    def set_setting(self, name: str, value: Any) -> None:
        self.__settings_menu.set_dict_value(name, value)
        self.update_screen()

    def on_created(self):
        if self.__first_message:
            self.send_message(self.__first_message)
        elif self.__prompt_file:
            self.__load_prompt(self.__prompt_file)

    def on_tab_pressed(self) -> bool:
        if not self.__show_more():
            self.__load_prompt()
        return True

    def send_message(
        self,
        text: str,
        tool_results: Optional[List[ToolResult]] = None,
    ) -> None:
        if self.__is_generating:
            return

        if text or tool_results:
            self.append_user_message(text, tool_results=tool_results)

        # Select the last line of the message being sent
        last_line_index = len(self.__lines) - 1
        if last_line_index >= 0:
            self.set_selection(last_line_index, last_line_index)

        self.__context = None
        self.__retry_count = 0
        self.__update_prompt()

        self.__complete_chat()

    def append_user_message(
        self,
        text: str,
        tool_results: Optional[List[ToolResult]] = None,
    ):
        msg_index = len(self.get_messages())

        message = Message(
            role="user",
            text=text,
            timestamp=datetime.now().timestamp(),
        )
        subindex = 0
        for text in text.splitlines():
            self.append_item(
                Line(role="user", text=text, msg_index=msg_index, subindex=subindex)
            )
            subindex += 1

        if self.__context:
            message["context"] = self.__context
            self.append_item(
                Line(
                    role="user",
                    msg_index=msg_index,
                    subindex=subindex,
                    context=self.__context,
                )
            )
            subindex += 1

        if self.__image_urls:
            message["image_urls"] = self.__image_urls.copy()
            for image_url in self.__image_urls:
                self.append_item(
                    Line(
                        role="user",
                        msg_index=msg_index,
                        subindex=subindex,
                        image_url=image_url,
                    )
                )
                subindex += 1
            self.__image_urls.clear()

        if tool_results:
            message["tool_result"] = tool_results

            for tool_result in tool_results:
                self.append_item(
                    Line(
                        role="user",
                        msg_index=msg_index,
                        subindex=subindex,
                        tool_result=tool_result,
                    )
                )

        self.get_messages().append(message)

        self.save_chat()
        self.update_screen()

    def get_tools(self) -> List[ToolDefinition]:
        return []

    def _get_tool_use_lines(
        self, tool_use: ToolUse, msg_index: int, subindex: int
    ) -> List[Line]:
        return [
            Line(
                role="assistant",
                msg_index=msg_index,
                subindex=subindex,
                tool_use=tool_use,
            )
        ]

    def on_tool_use_start(self, tool_use: ToolUse):
        pass

    def on_tool_use_args_delta(self, text: str):
        pass

    def on_tool_use(self, tool_use: ToolUse):
        pass

    def on_reasoning(self, reasoning: str):
        msg_index, subindex = self.get_message_index_and_subindex()
        line = Line(
            role="assistant",
            text=get_reasoning_text(reasoning),
            msg_index=msg_index,
            subindex=subindex,
            reasoning=reasoning,
        )
        self.append_item(line)
        self.process_events()

    def on_image(self, image_url: str):
        msg_index, subindex = self.get_message_index_and_subindex()
        line = Line(
            role="assistant",
            msg_index=msg_index,
            subindex=subindex,
            image_url=image_url,
        )
        self.append_item(line)
        self.process_events()

    def __complete_chat(self, status: Optional[str] = None):
        if self.__is_generating:
            return

        selected_model = get_model(self.get_settings()["model"])
        if (
            selected_model.provider == "llama_cpp"
            and not ensure_llama_cpp_server()
        ):
            return

        self.on_generating()
        if status:
            self.set_message(status)
        self.__is_generating = True
        self.__update_terminal_title(state="generating")

        self._out_message = out_message = Message(
            role="assistant",
            text="",
            timestamp=datetime.now().timestamp(),
        )
        messages = self.get_messages(expand_context=True)
        events: Queue[Callable[[], None]] = Queue()

        async def chat_task():
            try:
                chunk_index = 0
                async for chunk in await complete_chat(
                    messages=messages,
                    model=self.get_settings()["model"],
                    system_prompt=self.get_system_prompt(),
                    tools=self.get_tools(),
                    on_image=lambda image_url: events.put(
                        lambda: self.on_image(image_url)
                    ),
                    on_tool_use_start=lambda tool_use: events.put(
                        lambda: self.on_tool_use_start(tool_use)
                    ),
                    on_tool_use_args_delta=lambda text: events.put(
                        lambda: self.on_tool_use_args_delta(text)
                    ),
                    on_tool_use=lambda tool_use: events.put(
                        lambda: self.on_tool_use(tool_use)
                    ),
                    on_reasoning=lambda text: events.put(
                        lambda: self.on_reasoning(text)
                    ),
                    out_message=out_message,
                    usage=self.__usage,
                ):
                    events.put(
                        lambda chunk_index=chunk_index, chunk=chunk: (
                            self.__on_chat_chunk(chunk_index, chunk)
                        )
                    )
                    chunk_index += 1

                events.put(lambda: self.__on_chat_done())

            except asyncio.CancelledError:
                events.put(lambda: self.__on_chat_done(cancelled=True))

            except Exception as exception:
                events.put(
                    lambda exception=exception: self.__on_chat_exception(
                        exception=exception,
                    )
                )

        self.__chat_task = asyncio.run_coroutine_threadsafe(chat_task(), _loop)
        while self.__is_generating or not events.empty():
            try:
                events.get_nowait()()
            except Empty:
                self.process_events(timeout_sec=0.1)
                if self.__is_generating:
                    self.__spinner.advance()
                    self.update_screen()
        self.__chat_task = None

    def __on_chat_done(self, cancelled=False):
        assert self._out_message
        self.__is_generating = False
        self.__update_terminal_title(state="done")

        if cancelled:
            self._out_message["text"] += f"\n{_INTERRUPT_MESSAGE}"
            msg_index, subindex = self.get_message_index_and_subindex()
            self.append_item(
                Line(
                    role="assistant",
                    text=f"{_INTERRUPT_MESSAGE}",
                    msg_index=msg_index,
                    subindex=subindex,
                )
            )

        text = self._out_message["text"]
        self.get_messages().append(self._out_message)
        self.save_chat()
        self._out_message = None

        if not cancelled:
            if self.__copy:
                set_clip(text)
                self.close()
            elif self.__out_file:
                with open(self.__out_file, "w", encoding="utf-8") as f:
                    f.write(text)
                self.close()

            self.on_message(text)

        if self.__message_queue:
            if cancelled:
                self.__message_queue.clear()
                self.__update_prompt()
            else:
                next_text = self.__message_queue.pop(0)
                self.send_message(next_text)

    def __on_chat_chunk(self, chunk_index: int, chunk: str):
        for i, a in enumerate(chunk.split("\n")):
            if i > 0 or chunk_index == 0:
                msg_index, subindex = self.get_message_index_and_subindex()
                line = Line(
                    role="assistant",
                    msg_index=msg_index,
                    subindex=subindex,
                )
                self.append_item(line)
                if EXPERIMENTAL_FOLLOW_NEW_MESSAGE:
                    if subindex == 0:
                        self.goto_line(len(self.items) - 1)
            self.items[-1].text += a

        self.update_screen()

    def __on_chat_exception(self, exception: Exception):
        self.__is_generating = False
        self.__update_terminal_title(state="done")

        if self.get_settings()["retry"]:
            self.__retry_count += 1
            self.__complete_chat(status=f"retry {self.__retry_count}: {exception}")
        else:
            menu = ExceptionMenu(exception=exception)
            menu.exec()

    def save_chat(self):
        if self.__chat_file is None:
            return
        os.makedirs(os.path.dirname(self.__chat_file), exist_ok=True)
        save_json(self.__chat_file, self.__messages)
        self.__history_manager.delete_old_files()

    def __refresh_lines(self):
        self.__lines[:] = []
        for msg_index, message in enumerate(self.get_messages()):
            subindex = 0

            # Reasoning
            for reasoning in message.get("reasoning", []):
                self.__lines.append(
                    Line(
                        role=message["role"],
                        msg_index=msg_index,
                        subindex=subindex,
                        reasoning=reasoning,
                    )
                )
                subindex += 1

            # Text content
            if message["text"]:
                for line in message["text"].splitlines():
                    self.__lines.append(
                        Line(
                            role=message["role"],
                            msg_index=msg_index,
                            subindex=subindex,
                            text=line,
                        )
                    )
                    subindex += 1

            # Context
            context = message.get("context")
            if context:
                self.__lines.append(
                    Line(
                        role=message["role"],
                        msg_index=msg_index,
                        subindex=subindex,
                        context=context,
                    )
                )
                subindex += 1

            # Image file
            image_urls = message.get("image_urls", [])
            for image_url in image_urls:
                self.__lines.append(
                    Line(
                        role=message["role"],
                        msg_index=msg_index,
                        subindex=subindex,
                        image_url=image_url,
                    )
                )
                subindex += 1

            # Tool uses
            for tool_use in message.get("tool_use", []):
                for line in self._get_tool_use_lines(
                    tool_use, msg_index=msg_index, subindex=subindex
                ):
                    self.__lines.append(line)
                    subindex += 1

            # Tool results
            for tool_result in message.get("tool_result", []):
                self.__lines.append(
                    Line(
                        role=message["role"],
                        msg_index=msg_index,
                        subindex=subindex,
                        tool_result=tool_result,
                    )
                )
                subindex += 1

        self.update_screen()

    def load_chat(self, file: str):
        if not os.path.exists(file):
            self.set_message(f"Conv file not exist: {file}")
            return

        self.__chat_file = file
        self.__messages = load_json(self.__chat_file)
        self.__refresh_lines()
        self.__update_terminal_title()

    def clear_messages(self):
        self.__lines.clear()
        self.get_messages().clear()
        self.__usage.reset()
        self.__message_queue.clear()
        self.reset_selection()
        self.set_follow(True)
        self.update_screen()

    def new_chat(self):
        self.clear_messages()

        self.set_input("")
        self.__context = None
        self.__image_urls.clear()
        self.__update_prompt()
        self.__update_terminal_title(state="idle")

        self.__chat_file = self.__history_manager.get_new_file()

    def on_enter_pressed(self):
        text = self.get_input()
        if not text:
            return

        if self.__is_generating:
            self.__message_queue.append(text)
            self.clear_input()
            self.set_message(f"message queued ({len(self.__message_queue)})")
            self.__update_prompt()
            return

        if self.clear_input():
            self.send_message(text)

    def on_item_selection_changed(self, item: Optional[Line], i: int):
        self.__copy_mode = 0
        return super().on_item_selection_changed(item, i)

    def on_message(self, content: str):
        pass

    def on_generating(self):
        pass

    def on_response(self, text: str, done: bool):
        pass

    def get_status_text(self) -> str:
        parts = []
        if self.__is_generating:
            parts.append(self.__spinner.frame)
        model = str(self.get_settings().get("model", "")).split("/")[-1]
        if model:
            parts.append(model)
        if self.__usage.total_tokens or self.__usage.input_tokens:
            parts.append(f"{self.__usage}")
        return " ".join(parts) + "\n" + super().get_status_text()

    def get_system_prompt(self) -> str:
        return self.__system_prompt

    def on_escape_pressed(self):
        if not self.__cancel_chat_completion():
            super().on_escape_pressed()

    def __cancel_chat_completion(self) -> bool:
        if self.__is_generating:
            if self.__chat_task and not self.__chat_task.done():
                self.__chat_task.cancel()
            return True
        return False

    def paste(self) -> bool:
        if not super().paste():
            from PIL import Image, ImageGrab

            im = ImageGrab.grabclipboard()

            if isinstance(im, Image.Image):
                im = im.convert("RGB")
                fd, temp_path = tempfile.mkstemp(suffix=".png")
                os.close(fd)
                try:
                    im.save(temp_path)
                    self.__image_urls.append(encode_image_base64(temp_path))
                    self.__update_prompt()
                    return True
                finally:
                    os.remove(temp_path)

        return False


def _is_image_file(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in _IMAGE_EXTENSIONS


def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=str, nargs="?", help="input message")
    parser.add_argument(
        "-c",
        "--context",
        type=str,
        nargs="?",
        help="context file path or context text",
    )
    parser.add_argument("-i", "--in-file", type=str)
    parser.add_argument("-o", "--out-file", type=str)
    parser.add_argument("-m", "--model", type=str)
    parser.add_argument("-p", "--prompt-file", type=str)
    parser.add_argument("--copy", action="store_true")
    args = parser.parse_args()

    image_urls = None
    message = None

    if args.input and os.path.isfile(args.input):
        if _is_image_file(args.input):
            image_urls = [encode_image_base64(args.input)]
        else:
            with open(args.input, "r", encoding="utf-8") as f:
                message = f.read()
    elif args.in_file:
        with open(args.in_file, "r", encoding="utf-8") as f:
            message = f.read()
    elif not sys.stdin.isatty():
        message = sys.stdin.read()
    else:
        message = args.input

    chat = ChatMenu(
        message=message,
        context=args.context,
        image_urls=image_urls,
        out_file=args.out_file,
        model=args.model,
        copy=args.copy,
        prompt_file=args.prompt_file,
        data_dir=get_default_data_dir(),
    )
    chat.exec()


if __name__ == "__main__":
    _main()
