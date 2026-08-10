import datetime
import os
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional

from utils.clip import get_clip
from utils.jsonutil import load_json, save_json

from .menu import Menu


class InputMenu(Menu[str]):
    def __init__(
        self,
        items: Optional[List[str]] = None,
        prompt: str = "",
        history_list: Optional[List[str]] = None,
        history_file: Optional[str] = None,
        text="",
        show_clipboard: bool = False,
        return_selection_if_empty: bool = False,
        item_hotkey: Optional[Dict[str, str]] = None,
        item_hotkey_name: Optional[Dict[str, str]] = None,
        **kwargs,
    ):
        self.__history_list = history_list
        self.__history_file = history_file
        if self.__history_file:
            self.__history_data = load_json(
                self.__history_file, default={"history": []}
            )
        self.__items = items
        self.__return_selection_if_empty = return_selection_if_empty
        super().__init__(
            prompt=prompt,
            items=([get_clip()] if show_clipboard else [])
            + (
                self.__items
                if self.__items is not None
                else (self.__history_data["history"] if self.__history_file else [])
            ),
            text=text,
            **kwargs,
        )
        self.add_command(self.__insert_dir_path)
        self.add_command(self.__insert_file_path)
        self.add_command(self.__insert_date, hotkey="alt+d")
        self.add_command(self.__run_script_and_insert_output, hotkey="!")
        if item_hotkey is not None:
            for item, hotkey in item_hotkey.items():
                self.add_command(
                    func=lambda item=item: self._set_input_and_close(item),
                    hotkey=hotkey,
                    name=(item_hotkey_name or {}).get(item, f"select {item}"),
                    pinned=True,
                )

    def __run_script_and_insert_output(self):
        script_dir = os.path.realpath(os.path.dirname(__file__))
        myscripts_path = os.path.abspath(script_dir + "/../../../myscripts.py")
        with tempfile.NamedTemporaryFile() as tmpfile:
            ret_code = self.run_raw(
                lambda: subprocess.call(
                    [
                        sys.executable,
                        myscripts_path,
                        "--prompt",
                        "insert script output",
                        "--out-to-file",
                        tmpfile.name,
                    ],
                ),
            )
            if ret_code == 0:
                with open(tmpfile.name, "r", encoding="utf-8") as f:
                    out = f.read().strip()
                self.set_input(out)

    def _set_input_and_close(self, text: str):
        self.set_input(text)
        self.close()

    def request_input(self) -> Optional[str]:
        self.exec()

        text = self.get_text()
        if text is None:
            return None

        if self.__history_file:
            if text in self.__history_data["history"]:
                self.__history_data["history"].remove(text)
            self.__history_data["history"].insert(0, text)
            save_json(self.__history_file, self.__history_data)
        if self.__history_list is not None:
            if text in self.__history_list:
                self.__history_list.remove(text)
            self.__history_list.insert(0, text)
        if text.strip() == "" and self.__return_selection_if_empty:
            return self.get_selected_item()
        else:
            return text

    def __insert_dir_path(self):
        from .filemenu import FileMenu

        dir_path = FileMenu(
            goto=self.get_input(),
            prompt="insert dir path",
        ).select_directory()
        if dir_path is not None:
            self.set_input(dir_path)

    def __insert_file_path(self):
        from .filemenu import FileMenu

        file_path = FileMenu(
            goto=self.get_input(),
            prompt="insert file path",
        ).select_file()
        if file_path is not None:
            self.set_input(file_path)

    def __insert_date(self):
        self.set_input(datetime.datetime.now().strftime("%Y-%m-%d"))
