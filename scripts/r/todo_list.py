import argparse
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Literal, NotRequired, Optional, TypedDict

from utils.dateutil import format_timestamp, parse_datetime
from utils.editor import edit_text
from utils.menu.dicteditmenu import DictEditMenu
from utils.menu.inputdatemenu import input_date
from utils.menu.listeditmenu import ListEditMenu
from utils.textutil import truncate_text


class TodoItem(TypedDict):
    id: int
    description: str
    status: Literal["none", "closed", "in_progress"]
    due_ts: NotRequired[float]


_STATUS_SYMBOLS = {"closed": "[✓]", "in_progress": "[…]", "none": "[ ]"}
_STATUS_PRIORITY = {"in_progress": 0, "none": 1, "closed": 2}


def get_relative_time_str(ts: float) -> str:
    date = datetime.fromtimestamp(ts)
    now = datetime.now(date.tzinfo)
    diff = (date.date() - now.date()).days

    if diff == 0:
        return "today"
    else:
        sign = "+" if diff > 0 else "-"
        days = abs(diff)
        if days > 365:
            years, remainder = divmod(days, 365)
            months = remainder // 30
            return f"{sign}{years}y{f'{months}M' if months else ''}"
        elif days > 30:
            months, days = divmod(days, 30)
            return f"{sign}{months}M{f'{days}d' if days else ''}"
        else:
            return f"{sign}{days}d"


def get_pretty_ts(ts):
    date_str = format_timestamp(ts, show_hhmm=False).ljust(5)
    time_diff_str = get_relative_time_str(ts)
    return f"{time_diff_str:>7} {date_str}"


class _EditTodoItemMenu(DictEditMenu):
    def edit_dict_value(self, data: Dict[str, Any], name: str):
        if name in ("due_ts",):
            ts = input_date(
                prompt=name,
                default_ts=data[name],
            )
            if ts:
                data[name] = ts
        else:
            return super().edit_dict_value(data, name)

    def get_value_str(self, name: str, val: Any) -> str:
        if name in ("due_ts",):
            return format_timestamp(val)
        else:
            return super().get_value_str(name, val)


class TodoMenu(ListEditMenu[TodoItem]):
    def __init__(
        self,
        data_file: str,
    ):
        self.__last_tick = 0.0

        super().__init__(prompt="todo", json_file=data_file, backup_json=True)

        self.__sort_tasks()

        self.add_command(self.__duplicate_task, hotkey="ctrl+d")
        self.add_command(self.__edit_description, hotkey="ctrl+e")
        self.add_command(self.__edit_due, hotkey="alt+d")
        self.add_command(self.__new_task, hotkey="ctrl+n")
        self.add_command(self.__reload_and_sort, hotkey="ctrl+r")
        self.add_command(self.__set_status_wip, hotkey="alt+w")
        self.add_command(self.__toggle_status, hotkey="alt+x")

    def __new_task(self):
        self.__add_task_interactive(
            {
                "id": self.get_next_id(),
                "status": "none",
                "description": "",
                "due_ts": parse_datetime("today").timestamp(),
            }
        )

    def __duplicate_task(self):
        selected = self.get_selected_item()
        if selected:
            item = selected.copy()
            item["status"] = "none"
            item["due_ts"] = parse_datetime("today").timestamp()
            self.__add_task_interactive(item)

    def __add_task_interactive(self, item: TodoItem):
        self.__edit_item_description(item)
        if not item["description"]:
            return
        self.__add_item(item)

    def __toggle_status(self):
        items = list(self.get_selected_items())
        if items:
            status_order = ("none", "closed")
            for item in items:
                current = item.get("status", "none")
                try:
                    idx = status_order.index(current)
                except ValueError:
                    idx = 0
                item["status"] = status_order[(idx + 1) % len(status_order)]
            self.save_json()
            self.update_screen()

    def get_item_text(self, item: TodoItem) -> str:
        # Date
        ts = item.get("due_ts")
        if ts:
            date_str = f"{get_pretty_ts(ts):<13}"
            if (
                item.get("status") not in ("closed", "in_progress")
                and datetime.fromtimestamp(ts) < datetime.now()
            ):
                date_str = f"\x1b[31m{date_str}\x1b[0m"
        else:
            date_str = " " * 13

        # Description
        desc = truncate_text(item["description"], max_lines=1)

        return f"{_STATUS_SYMBOLS[item['status']]} {date_str}  {desc}"

    def get_item_metadata(self, item: TodoItem) -> str:
        return _get_todo_str(item)

    def get_item_color(self, item: TodoItem) -> str:
        status = item["status"]
        if status == "in_progress":
            return "green"
        if status == "closed":
            return "blue"

        return "white"

    def on_enter_pressed(self):
        selected = self.get_selected_item()
        if selected:
            self.__edit_todo_item(selected)

    def on_idle(self):
        now = time.time()
        if now > self.__last_tick + 1.0:
            self.__last_tick = now
            self.__reload()

    def __reload_and_sort(self):
        self.__reload(force_sort=True)

    def on_escape_pressed(self):
        if not self.clear_input():
            if len(self.items) > 0:
                self.set_selected_item(self.items[0])

    def save_json(self):
        try:
            super().save_json()
        except Exception as e:
            self.set_message(f"Error on saving: {e}")

    def load_json(self) -> bool:
        try:
            if super().load_json():
                self.__ensure_ids()
                return True
            return False
        except Exception as e:
            self.set_message(f"Error on loading: {e}")
            return False

    def __ensure_ids(self):
        for item in self.items:
            if "id" not in item:
                item["id"] = self.get_next_id()

    def get_next_id(self) -> int:
        return max((item.get("id", 0) for item in self.items), default=0) + 1

    def __add_item(self, item: TodoItem):
        self.items.append(item)
        self.__sort_tasks()
        self.save_json()
        self.set_selected_item(item)

    def open_ai_agent(self, extra_args: Optional[List[str]] = None):
        prompt_file = os.path.join(os.path.dirname(__file__), "ai/skills/todo-list.md")
        args = [
            "--system-prompt",
            prompt_file,
        ]
        if extra_args:
            args += extra_args
        super().open_ai_agent(extra_args=args)

    def __edit_timestamp_field(self, items: List[TodoItem]):
        prompt = "date" if len(items) == 1 else "date for %d items" % len(items)
        default_ts = items[0].get("due_ts") if len(items) == 1 else None
        ts = input_date(prompt=prompt, default_ts=default_ts)
        if ts is None:
            return

        for item in items:
            if ts <= 0.0:
                item.pop("due_ts", None)
            else:
                item["due_ts"] = ts
        self.save_json()
        self.update_screen()

    def __edit_due(self):
        items = list(self.get_selected_items())
        if items:
            self.__edit_timestamp_field(items)

    def __edit_description(self):
        selected = self.get_selected_item()
        if selected:
            self.__edit_item_description(selected)

    def __edit_item_description(self, item: TodoItem):
        new_text = self.run_raw(
            lambda: edit_text(item["description"], tmp_file_ext=".md")
        )
        if new_text != item["description"]:
            item["description"] = new_text
            self.save_json()
            self.update_screen()

    def __edit_todo_item(self, item: TodoItem):
        _EditTodoItemMenu(
            item,
            on_dict_update=lambda _: self.save_json(),
        ).exec()

    def __reload(self, force_sort=False):
        if self.load_json():
            mtime_str = datetime.fromtimestamp(self.last_mtime).strftime("%H:%M:%S")
            self.set_message(f"reloaded ({mtime_str})")
            force_sort = True

        if force_sort:
            self.__sort_tasks()

    def __sort_tasks(self):
        selected = self.get_selected_item()
        self.items.sort(
            key=lambda item: (
                _STATUS_PRIORITY.get(item.get("status", "none"), 1),
                (
                    -item.get("due_ts", 0.0)
                    if item.get("status", "none") == "closed"
                    else item.get("due_ts", sys.float_info.max)
                ),
                item.get("description"),
            ),
        )
        self.refresh()
        self.set_selected_item(selected)

    def __set_status_wip(self):
        items = list(self.get_selected_items())
        if items:
            for item in items:
                item["status"] = "in_progress"
            self.save_json()
            self.update_screen()


def _add_todo(data_file: str, desc: str, due: Optional[str] = None):
    menu = TodoMenu(data_file=data_file)
    item: TodoItem = {
        "id": menu.get_next_id(),
        "description": desc,
        "status": "none",
        "due_ts": parse_datetime("today").timestamp(),
    }
    if due:
        try:
            dt = parse_datetime(due)
            item["due_ts"] = dt.timestamp()
        except ValueError:
            print(f"Error: Invalid date format: {due}")
            sys.exit(1)
    menu.items.append(item)
    menu.save_json()
    print("Todo item added:")
    _print_todo(item)


def _delete_todo(data_file: str, todo_id: int):
    menu = TodoMenu(data_file=data_file)
    item_to_delete = next(
        (item for item in menu.items if item.get("id") == todo_id), None
    )
    if item_to_delete:
        menu.items.remove(item_to_delete)
        menu.save_json()
        print(f"Todo item deleted (id={todo_id})")
    else:
        print(f"Todo item not found (id={todo_id})")
        sys.exit(1)


def _edit_todo(
    data_file: str,
    todo_id: int,
    desc: Optional[str] = None,
    status: Optional[str] = None,
    due: Optional[str] = None,
):
    menu = TodoMenu(data_file=data_file)
    item = next((item for item in menu.items if item.get("id") == todo_id), None)
    if not item:
        print(f"Todo item not found (id={todo_id})")
        sys.exit(1)

    if desc is not None:
        item["description"] = desc
    if status is not None:
        item["status"] = status  # type: ignore
    if due is not None:
        try:
            dt = parse_datetime(due)
            item["due_ts"] = dt.timestamp()
        except ValueError:
            print(f"Error: Invalid date format: {due}")
            sys.exit(1)

    menu.save_json()
    print("Todo item updated:")
    _print_todo(item)


def _get_todo_str(item: TodoItem) -> str:
    ts = item.get("due_ts")
    due_str = format_timestamp(ts, show_year=True) if ts else "None"

    desc = item.get("description", "")
    if "\n" in desc:
        desc_str = "Description: |\n" + "\n".join(
            f"  {line}" for line in desc.splitlines()
        )
    else:
        desc_str = f"Description: {desc}"

    return "\n".join(
        [
            "<todo-item>",
            f"ID: {item.get('id', 0)}",
            f"Status: {item.get('status', 'None')}",
            f"Due: {due_str}",
            desc_str,
            "</todo-item>",
        ]
    )


def _print_todo(item: TodoItem):
    print(_get_todo_str(item))


def _print_todos(items: List[TodoItem]):
    for item in items:
        _print_todo(item)


def _list_todos(data_file: str, show_all: bool = False):
    menu = TodoMenu(data_file=data_file)
    filtered_items = [
        item for item in menu.items if show_all or item.get("status") != "closed"
    ]
    _print_todos(filtered_items)


def _search_todos(data_file: str, query: str):
    menu = TodoMenu(data_file=data_file)
    query = query.lower()
    filtered_items = [
        item for item in menu.items if query in item.get("description", "").lower()
    ]
    _print_todos(filtered_items)


def _main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--data-file",
        type=str,
        help="Path to todo list data file",
        default=os.environ.get("TODO_DATA_FILE"),
    )

    subparsers = parser.add_subparsers(dest="command")

    add_parser = subparsers.add_parser("add", help="Add a new todo item")
    add_parser.add_argument(
        "--desc", required=True, help="Description of the todo item"
    )
    add_parser.add_argument("--due", help="Due date/time")

    delete_parser = subparsers.add_parser("delete", help="Delete a todo item")
    delete_parser.add_argument("id", type=int, help="ID of the todo item to delete")

    edit_parser = subparsers.add_parser("edit", help="Edit an existing todo item")
    edit_parser.add_argument("id", type=int, help="ID of the todo item to edit")
    edit_parser.add_argument("--desc", help="New description for the todo item")
    edit_parser.add_argument("--due", help="New due date/time")
    edit_parser.add_argument(
        "--status", choices=["none", "closed", "in_progress"], help="New status"
    )

    list_parser = subparsers.add_parser("list", help="List todo items")
    list_parser.add_argument(
        "--all", action="store_true", help="Show all items including closed ones"
    )

    search_parser = subparsers.add_parser("search", help="Search todo items")
    search_parser.add_argument("query", help="Search query")

    args = parser.parse_args()

    if args.command == "add":
        _add_todo(data_file=args.data_file, desc=args.desc, due=args.due)
    elif args.command == "delete":
        _delete_todo(data_file=args.data_file, todo_id=args.id)
    elif args.command == "edit":
        _edit_todo(
            data_file=args.data_file,
            todo_id=args.id,
            desc=args.desc,
            status=args.status,
            due=args.due,
        )
    elif args.command == "list":
        _list_todos(data_file=args.data_file, show_all=args.all)
    elif args.command == "search":
        _search_todos(data_file=args.data_file, query=args.query)
    else:
        menu = TodoMenu(data_file=args.data_file)
        menu.exec()


if __name__ == "__main__":
    _main()
