import csv
import os
from typing import List, Optional, OrderedDict

from utils.clip import set_clip
from utils.jsonutil import load_json, save_json
from utils.menu.confirmmenu import confirm

from .menu import Menu
from .inputmenu import InputMenu

MAX_COLUMN_WIDTH = 12

COLUMN_SEPARATOR = "  "


def format_text(s: str, column_width: int, row_index: int, is_last_column: bool) -> str:
    s = s.replace("\n", " ")
    if row_index == 0:
        s = s.upper()
    if is_last_column:
        return s
    return (
        (s[:MAX_COLUMN_WIDTH]).ljust(MAX_COLUMN_WIDTH)
        if column_width > MAX_COLUMN_WIDTH
        else s.ljust(column_width)
    )


class CsvData:
    def __init__(self, file: str) -> None:
        self.__rows: List[List[str]] = []
        self.__file = file
        self.__mtime = 0.0
        self.column_width: List[int] = []

        self.load_csv()

        self.__calculate_column_width()

    def get_header(self) -> List[str]:
        return self.__rows[0]

    def get_column_index(self, name: str) -> int:
        return self.get_header().index(name)

    def sort_by_column(self, name: str, desc=False):
        col_index = self.get_column_index(name)
        self.__rows[1:] = sorted(
            self.__rows[1:], key=lambda x: x[col_index], reverse=desc
        )

    def get_cell(self, row_index: int, name: str) -> str:
        col_index = self.get_column_index(name)
        return self.__rows[row_index][col_index]

    def set_cell(self, row_index: int, name: str, value: str):
        col_index = self.get_column_index(name)
        self.__rows[row_index][col_index] = value
        self.__calculate_column_width()

    def get_row_list(self, row_index) -> List[str]:
        return self.__rows[row_index]

    def get_row_dict(self, row_index: int) -> OrderedDict[str, str]:
        d: OrderedDict[str, str] = OrderedDict()
        for name, val in zip(self.get_header(), self.__rows[row_index]):
            d[name] = val
        return d

    def get_row_count(self) -> int:
        return len(self.__rows)

    def load_csv(self) -> bool:
        # Check if the file has been modified since last time
        mtime = os.path.getmtime(self.__file)
        if mtime > self.__mtime:
            # Read from CSV file
            self.__rows.clear()
            with open(self.__file, encoding="utf-8") as csvfile:
                reader = csv.reader(csvfile)
                for row in reader:
                    self.__rows.append(row)

            # Update modified time
            self.__mtime = mtime
            return True
        else:
            return False

    def save_csv(self) -> None:
        # Check if the file has been externally modified
        mtime = os.path.getmtime(self.__file)
        if mtime > self.__mtime:
            raise RuntimeError("CSV file has been modified externally")

        # Write to CSV file
        with open(self.__file, mode="w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(self.__rows)

        # Update modified time
        self.__mtime = os.path.getmtime(self.__file)

    def add_column(self, name: str, index: Optional[int] = None):
        if len(self.__rows) == 0:
            self.__rows.append([])
        if index is None:
            index = len(self.__rows[0])
        for i, row in enumerate(self.__rows):
            row.insert(index, name if i == 0 else "")
        self.__calculate_column_width()

    def add_row(
        self, values: Optional[List[str]] = None, index: Optional[int] = None
    ) -> int:
        num_columns = len(self.get_header())
        if values is None:
            values = [""] * num_columns
        elif len(values) != num_columns:
            raise Exception(f"{num_columns} elements are required based on the header.")

        if index is None:
            index = len(self.__rows)
        self.__rows.insert(index, values)
        self.__calculate_column_width()
        return index

    def delete_row(self, row_index: int) -> None:
        if row_index < 0 or row_index >= len(self.__rows):
            raise IndexError(f"Row index {row_index} out of bounds.")
        del self.__rows[row_index]
        self.__calculate_column_width()

    def get_unique_values_for_column(self, name: str) -> List[str]:
        col_index = self.get_column_index(name)
        return list(set([row[col_index] for row in self.__rows[1:]]))

    def duplicate_row(self, row_index: int) -> int:
        if row_index < 0 or row_index >= len(self.__rows):
            raise IndexError(f"Row index {row_index} out of bounds.")

        duplicated_values = self.__rows[row_index].copy()
        return self.add_row(duplicated_values, row_index + 1)

    def __calculate_column_width(self):
        self.column_width.clear()
        for col_index in range(len(self.get_header())):
            max_width = 0
            for row in self.__rows:
                max_width = max(max_width, len(row[col_index]))
            self.column_width.append(max_width)


class CsvRow:
    def __init__(self, df: CsvData, row_index: int) -> None:
        self.df = df
        self.row_index = row_index

    def __str__(self) -> str:
        return " ".join(self.df.get_row_list(self.row_index))


def _get_setting_file(csv_file: str) -> str:
    tmp_dir = os.path.join(os.path.dirname(csv_file), "tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    return os.path.join(tmp_dir, "csvmenu_setting.json")


class CsvMenu(Menu[CsvRow]):
    def __init__(self, csv_file: str, text: str = ""):
        self.__setting_file = _get_setting_file(csv_file)
        self.__settings = load_json(self.__setting_file, default={})

        self.df = CsvData(csv_file)

        self._rows: List[CsvRow] = []
        self.__update_rows()

        self._select_row = False
        self._selected_column = 0

        super().__init__(
            items=self._rows,
            text=text,
            prompt="/",
            timeout_sec=1.0,
        )

        self.add_command(self.__add_column, hotkey="alt+c")
        self.add_command(self.__add_row)
        self.add_command(self.__add_row_before, hotkey="alt+n")
        self.add_command(self.__add_row_after, hotkey="ctrl+n")
        self.add_command(self.__duplicate_row, hotkey="ctrl+d")
        self.add_command(self.__delete_row, hotkey="ctrl+k")
        self.add_command(self.__save, hotkey="ctrl+s")
        self.add_command(self.__copy_selected_cell, hotkey="ctrl+y", override=True)
        self.add_command(self.__sort_by_column, hotkey="alt+s")
        self.add_command(self.__select_prev_column, hotkey="left")
        self.add_command(self.__select_next_column, hotkey="right")

        if "selected_row" in self.__settings:
            row = self.__settings["selected_row"]
            if row >= 0:
                self.set_selected_row(row)

    def __save_settings(self):
        save_json(self.__setting_file, self.__settings)

    def __sort_by_column(self):
        menu = Menu(items=self.df.get_header(), prompt="sort by")
        menu.exec()
        name = menu.get_selected_item()
        if name is not None:
            self.df.sort_by_column(name=name)
            self.update_screen()

    def __save(self):
        self.df.save_csv()
        self.set_message("saved")

    def __copy_selected_cell(self):
        row = self.get_selected_item()
        if row is not None:
            value = self.df.get_row_list(row.row_index)[self._selected_column]
            set_clip(value)
            self.set_message(f"copied: {value}")

    def __update_rows(self):
        self._rows.clear()
        for row_index in range(self.df.get_row_count()):
            self._rows.append(CsvRow(df=self.df, row_index=row_index))

    def on_enter_pressed(self):
        if self._select_row:
            super().on_enter_pressed()
            return

        row = self.get_selected_item()
        if row is not None:
            self.__edit_cell(row.row_index)

    def __edit_cell(self, row_index: int):
        name = self.df.get_header()[self._selected_column]
        value = self.df.get_row_list(row_index)[self._selected_column]
        new_value = InputMenu(
            prompt=f"edit {name}",
            text=value,
            items=self.df.get_unique_values_for_column(name),
        ).request_input()
        if new_value is not None and new_value != value:
            self.df.set_cell(row_index, name, new_value)
            self.df.save_csv()
            self.update_screen()

    def __select_prev_column(self):
        if not self._select_row:
            self._selected_column = max(self._selected_column - 1, 0)
            self.__scroll_selected_column_into_view()

    def __select_next_column(self):
        if not self._select_row:
            self._selected_column = min(
                self._selected_column + 1, len(self.df.get_header()) - 1
            )
            self.__scroll_selected_column_into_view()

    def __scroll_selected_column_into_view(self):
        start = sum(
            min(width, MAX_COLUMN_WIDTH) + len(COLUMN_SEPARATOR)
            for width in self.df.column_width[: self._selected_column]
        )
        width = min(
            self.df.column_width[self._selected_column], MAX_COLUMN_WIDTH
        )
        self.scroll_horizontal_into_view(start, start + width)

    def get_item_text(self, item: CsvRow) -> str:
        row = self.df.get_row_list(item.row_index)
        cells = [
            format_text(
                text,
                column_width=self.df.column_width[i],
                row_index=item.row_index,
                is_last_column=i == len(row) - 1,
            )
            for i, text in enumerate(map(str, row))
        ]
        selected_row = self.get_selected_item()
        if not self._select_row and selected_row is item:
            cells[self._selected_column] = (
                "\x1b[27m" + cells[self._selected_column] + "\x1b[7m"
            )
            return "\x1b[7m" + COLUMN_SEPARATOR.join(cells) + "\x1b[27m"
        return COLUMN_SEPARATOR.join(cells)

    def __add_column(self):
        name = InputMenu(prompt="New column name").request_input()
        if name is not None and name != "":
            self.df.add_column(name=name)
            self.df.save_csv()
            self.__update_rows()
            self.set_message(f'added column "{name}"')

    def __add_row(self, row_index=None):
        row_index = self.df.add_row(index=row_index)
        self.df.save_csv()
        self.__update_rows()
        self.set_selected_row(row_index)
        self.__edit_cell(row_index)

    def __add_row_before(self):
        row = self.get_selected_item()
        if row is not None:
            self.__add_row(row_index=row.row_index)

    def __add_row_after(self):
        row = self.get_selected_item()
        if row is not None:
            self.__add_row(row_index=row.row_index + 1)

    def __duplicate_row(self):
        row = self.get_selected_item()
        if row is not None:
            dup_row_index = self.df.duplicate_row(row.row_index)
            self.df.save_csv()
            self.__update_rows()
            self.set_selected_row(dup_row_index)
            self.__edit_cell(dup_row_index)

    def __delete_row(self):
        row = self.get_selected_item()
        if row is not None:
            if confirm('Delete row "{row}"?'):
                self.df.delete_row(row_index=row.row_index)
                self.df.save_csv()
                self.__update_rows()

    def select_row(self) -> int:
        try:
            self._select_row = True
            return self.exec()
        finally:
            self._select_row = False

    def on_item_selection_changed(self, item: Optional[CsvRow], i: int):
        self.__settings["selected_row"] = i
        self.__save_settings()

    def on_timeout(self):
        if self.df.load_csv():
            self.__update_rows()
            self.set_message("CSV file reloaded")
