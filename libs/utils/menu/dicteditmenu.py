from collections import OrderedDict
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
)

from utils.clip import get_clip, set_clip
from utils.editor import edit_text
from utils.jsonschema import JSONSchema

from .menu import Menu
from .listeditmenu import ListEditMenu
from .valueeditmenu import ValueEditMenu


def _infer_schema_type(value: Any) -> JSONSchema:
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    if isinstance(value, str):
        return {"type": "string"}
    raise Exception(f"Unsupported value type: {type(value)}")


class _KeyValuePair:
    def __init__(
        self,
        dict: Dict[str, Any],
        key: str,
        key_display_width: int,
        get_value_str: Callable[[str, str], str],
        default_dict: Dict[str, Any] = {},
    ) -> None:
        self.key = key

        self.__default_dict = default_dict
        self.__dict = dict
        self.__get_value_str = get_value_str
        self.__key_display_width = key_display_width

    def __str__(self) -> str:
        sep = " : "
        if self.key in self.__dict:
            value = self.__dict[self.key]
        elif self.key in self.__default_dict:
            value = self.__default_dict[self.key]
        else:
            value = ""
        is_modified = (
            bool(self.__default_dict) and value != self.__default_dict[self.key]
        )
        header = self.key.ljust(self.__key_display_width)
        if isinstance(value, str):
            # Indent string value.
            value = "\n".join(
                (
                    (" " * (self.__key_display_width + len(sep))) + line
                    if i > 0
                    else line
                )
                for i, line in enumerate(value.splitlines())
            )
        return "{}{}{}{}".format(
            header,
            sep,
            self.__get_value_str(self.key, value),
            " (*)" if is_modified else "",
        )


class DictEditMenu(Menu[_KeyValuePair]):
    def __init__(
        self,
        data,
        default_dict: Optional[Dict[str, Any]] = None,
        on_dict_update: Optional[Callable[[Dict], None]] = None,
        dict_history: Dict[str, List[Any]] = {},
        on_dict_history_update: Optional[Callable[[Dict[str, List[Any]]], None]] = None,
        prompt="",
        schema: Optional[JSONSchema] = None,
    ):
        self.__data = data
        self.__default_dict: Dict[str, Any] = default_dict or {}
        self.__dict_history = dict_history
        self.__on_dict_history_update = on_dict_history_update
        self.__on_dict_update = on_dict_update
        self.__schema: Optional[JSONSchema] = schema

        super().__init__(
            prompt=prompt,
            highlight=OrderedDict([(r"\(\*\)", "green")]),
            wrap_text=True,
        )

        self.__init_items()

        self.add_command(self.__copy_selected_dict_value, hotkey="ctrl+y")
        self.add_command(self.__prev_value, hotkey="left")
        self.add_command(self.__next_value, hotkey="right")
        self.add_command(self.__paste_value, hotkey="ctrl+v", override=True)
        self.add_command(self.__edit_value, hotkey="ctrl+e")
        self.add_command(self.__reset_value, hotkey="ctrl+k")
        self.add_command(self.__reset_value, hotkey="delete")

    def __prev_value(self):
        self.__prev_or_next_value(prev=True)

    def __next_value(self):
        self.__prev_or_next_value(prev=False)

    def __prev_or_next_value(self, prev=False):
        key = self.get_selected_key()
        if key is not None:
            value = self.__data[key]
            if isinstance(value, bool):
                self.__data[key] = not self.__data[key]
                self.__notify_dict_updated()
                self.update_screen()
            elif isinstance(value, str):
                if self.__dict_history and key in self.__dict_history:
                    values = self.__dict_history[key]
                    try:
                        index = values.index(value)
                        index = (
                            min(index + 1, len(values) - 1)
                            if prev
                            else max(0, index - 1)
                        )
                        self.__data[key] = values[index]
                        self.__notify_dict_updated()
                    except ValueError:
                        pass

    def __reset_value(self):
        key = self.get_selected_key()
        if key is None:
            return

        default_values = self.get_default_values()
        if key not in default_values:
            return

        self.__data[key] = default_values[key]
        self.__notify_dict_updated()

    def __edit_value(self):
        key = self.get_selected_key()
        if key is not None:
            value = self.__data[key]
            if isinstance(value, str):
                new_value = self.run_raw(lambda: edit_text(value))
                if new_value != value:
                    self.set_dict_value(key, new_value)

    def __paste_value(self):
        key = self.get_selected_key()
        if key is not None:
            value = self.__data[key]
            if isinstance(value, str):
                val = get_clip()
                self.set_dict_value(key, val)

    def __copy_selected_dict_value(self):
        key = self.get_selected_key()
        if key is not None:
            value = self.__data[key]
            set_clip(value)
            self.set_message(f"copied: {value}")

    def __notify_dict_updated(self):
        self.on_dict_update(self.__data)
        if self.__on_dict_history_update:
            self.__on_dict_history_update(self.__dict_history)
        self.update_screen()

    def __init_items(self):
        default_dict = self.get_default_values()

        # Get keys
        keys = set(self.__data.keys())
        if default_dict:
            keys.update(default_dict.keys())
        schema = self.get_schema()
        if schema:
            assert schema["type"] == "object"
            keys.update(schema["properties"].keys())

        # Get max width for keys
        max_width = max((len(x) for x in keys), default=0) + 1

        kvps: List[Tuple[str, bool]] = []
        for key in keys:
            modified = (
                bool(default_dict)
                and key in self.__data
                and self.__data[key] != default_dict[key]
            )
            kvps.append((key, modified))

        # Sort alphabetically, modified values first
        kvps = sorted(kvps, key=lambda x: (not x[1], x[0]))

        # Update items
        self.items.clear()
        for key, _ in kvps:
            self.items.append(
                _KeyValuePair(
                    self.__data,
                    key=key,
                    key_display_width=max_width,
                    default_dict=default_dict,
                    get_value_str=self.get_value_str,
                )
            )

    def on_enter_pressed(self):
        self.__edit_dict_value()

    def get_selected_key(self) -> Optional[str]:
        selected = self.get_selected_item()
        if selected is not None:
            return selected.key
        else:
            return None

    def get_default_values(self) -> Dict[str, Any]:
        return self.__default_dict

    def get_schema(self) -> Optional[JSONSchema]:
        return self.__schema

    def __get_dict_history_values(self, name: str) -> List[str]:
        if name not in self.__dict_history:
            dict_history_values = self.__dict_history[name] = []
        else:
            dict_history_values = self.__dict_history[name]
        return dict_history_values

    def __edit_dict_value(self):
        name = self.get_selected_key()
        if name is None:
            return

        self.edit_dict_value(data=self.__data, name=name)

        self.__notify_dict_updated()
        self.update_screen()

    def get_value(self, name: str):
        return self.__data[name]

    def set_dict_value(self, name: str, value: str):
        # Update dict
        self.__data[name] = value

        # Update dict history
        dict_history_values = self.__get_dict_history_values(name)
        if value in dict_history_values:  # avoid duplicates
            dict_history_values.remove(value)
        dict_history_values.insert(0, value)

        self.__notify_dict_updated()
        self.update_screen()

    def edit_dict_value(self, data: Dict[str, Any], name: str):
        default_dict = self.get_default_values()
        schema = self.get_schema()

        data_type: JSONSchema
        if schema:
            assert schema["type"] == "object"
            data_type = schema["properties"][name]
        elif default_dict and name in default_dict:
            data_type = _infer_schema_type(default_dict[name])
        elif name in data:
            data_type = _infer_schema_type(data[name])
        else:
            raise Exception(f"Missing schema and default_dict for key {name}")
        if data_type["type"] == "array":
            list_values = data[name]
            ListEditMenu(
                list_values,
                item_type=data_type["items"],
                prompt=f"edit {name}",
            ).exec()
        else:
            dict_history_values = self.__get_dict_history_values(name)
            menu = ValueEditMenu(
                value=data[name] if name in data else None,
                prompt=name,
                type=data_type,
                items=dict_history_values,
                dict_history_values=dict_history_values,
            )
            menu.exec()
            if not menu.is_cancelled:
                data[name] = menu.value

    def get_value_str(self, name: str, val: Any) -> str:
        return str(val)

    def on_dict_update(self, data):
        if self.__on_dict_update:
            self.__on_dict_update(self.__data)
