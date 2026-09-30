import os
from typing import Generic, List, Optional, TypeVar

from utils.jsonschema import JSONSchema
from utils.jsonutil import save_json, try_load_json, try_save_json
from .menu import Menu
from utils.menu.confirmmenu import ConfirmMenu
from utils.menu.valueeditmenu import ValueEditMenu

T = TypeVar("T")


class ListEditMenu(Menu, Generic[T]):
    def __init__(
        self,
        items: Optional[List[T]] = None,
        json_file: Optional[str] = None,
        backup_json=False,
        item_type: Optional[JSONSchema] = None,
        **kwargs,
    ):
        self.__backup_json = backup_json
        self.__json_file = json_file
        self.__last_mtime = 0.0
        self.__item_type = item_type

        super().__init__(items=items if items is not None else [], **kwargs)

        self.load_json()

        self.add_command(self.__new_item, hotkey="ctrl+n")
        self.add_command(self.__delete_item, hotkey="ctrl+k")
        self.add_command(self.__delete_item, hotkey="delete")
        self.add_command(self.__force_save, hotkey="ctrl+s")

    @property
    def last_mtime(self) -> float:
        return self.__last_mtime

    def load_json(self) -> bool:
        if self.__json_file is not None:
            result = try_load_json(
                self.__json_file, default=[], last_mtime=self.__last_mtime
            )
            if result is not None:
                self.items[:], self.__last_mtime = result
                if not isinstance(self.items[:], list):
                    raise TypeError("JSON data must be a list")
                return True
        return False

    def __new_item(self):
        self.__edit_or_add_item()

    def __edit_or_add_item(self, index=-1):
        if not self.__item_type:
            return

        if self.__item_type["type"] == "object":
            from utils.menu.dicteditmenu import DictEditMenu

            if index >= 0:
                data = self.items[index]
                prompt = f"edit item[{index}]"
            else:
                data = {}
                self.items.append(data)
                prompt = "add item"

            menu = DictEditMenu(
                data=data,
                schema=self.__item_type,
                prompt=prompt,
            )
            menu.exec()
        else:
            if index >= 0:
                value = self.items[index]
                prompt = "edit item"
            else:
                value = None
                prompt = "add item"

            menu = ValueEditMenu(
                prompt=prompt,
                type=self.__item_type,
                value=value,
            )
            menu.exec()
            if menu.is_cancelled:
                return

            if index >= 0:
                self.items[index] = menu.value
            else:
                self.items.append(menu.value)

    def __delete_item(self):
        index = self.get_selected_index()
        if 0 <= index < len(self.items):
            confirm_menu = ConfirmMenu(prompt="delete item?")
            confirm_menu.exec()
            if confirm_menu.is_confirmed():
                del self.items[index]
                self.update_screen()
                self.save_json()

    def append_item(self, item: T):
        self.items.append(item)
        self.update_screen()
        self.save_json()

    def clear(self):
        self.items.clear()
        self.update_screen()
        self.save_json()

    def get_json_items(self) -> List[T]:
        return self.items

    def save_json(self):
        if self.__json_file:
            self.__last_mtime = try_save_json(
                self.__json_file,
                self.get_json_items(),
                last_mtime=self.__last_mtime,
                backup=self.__backup_json,
            )

    def __force_save(self):
        if self.__json_file:
            save_json(self.__json_file, self.get_json_items())
            self.__last_mtime = os.path.getmtime(self.__json_file)
            self.set_message("force saved")

    def on_enter_pressed(self):
        index = self.get_selected_index()
        if index < 0:
            return
        self.__edit_or_add_item(index)
