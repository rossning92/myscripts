import csv
import datetime
import os
from typing import List, Optional, OrderedDict

from utils.editor import edit_text
from utils.jsonutil import load_json, save_json
from utils.menu.confirmmenu import confirm

from .menu import Menu
from .inputmenu import InputMenu

MAX_COLUMN_WIDTH = 16

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


class CsvCell:
    def __init__(
        self,
        df: CsvData,
        row_index: int,
        name: str,
        max_column_name_width: int,
    ) -> None:
        self.df = df
        self.row_index = row_index
        self.name = name
        self.max_column_name_width = max_column_name_width

    def __str__(self) -> str:
        cell_value = str(self.df.get_cell(self.row_index, self.name))
        lines = cell_value.splitlines()
        header = self.name.ljust(self.max_column_name_width, " ") + " : "
        indented_lines = "\n".join(
            ((" " * (self.max_column_name_width + 3)) + line if i > 0 else line)
            for i, line in enumerate(lines)
        )
        return header + indented_lines


class CsvRow:
    def __init__(self, df: CsvData, row_index: int) -> None:
        self.df = df
        self.row_index = row_index

    def __str__(self) -> str:
        return " ".join(self.df.get_row_list(self.row_index))


class RowMenu(Menu[CsvCell]):
    def __init__(self, df: CsvData, row_index: int) -> None:
        self.df = df
        self.row_index = row_index
        self.selected_cell: Optional[CsvCell] = None

        self.cells: List[CsvCell] = []
        self._initialize_cells()

        super().__init__(
            items=self.cells,
            wrap_text=True,
            prompt=f"row {row_index}",
        )

        self.add_command(
            lambda: self.run_raw(
                lambda: self.edit_cell(external_editor=True)
            ),
            hotkey="ctrl+e",
            name="edit_cell_in_editor",
        )
        self.add_command(
            self._prev_row,
            hotkey="left",
        )
        self.add_command(
            self._next_row,
            hotkey="right",
        )
        self.add_command(
            self._insert_datetime,
            hotkey="alt+d",
            name="insert_datetime",
        )

    def _goto_row(self, row_index: int):
        self.row_index = row_index
        self.set_prompt(f"row {row_index}")
        self._initialize_cells()
        self.update_screen()

    def _prev_row(self):
        self._goto_row(max(self.row_index - 1, 0))

    def _next_row(self):
        self._goto_row(min(self.row_index + 1, self.df.get_row_count() - 1))

    def _insert_datetime(self):
        cell = self.get_selected_item()
        if cell is not None:
            now = datetime.datetime.now()
            datetime_str = now.strftime("%Y-%m-%d %H:%M")
            self.df.set_cell(self.row_index, cell.name, datetime_str)
            self.df.save_csv()
            self.update_screen()

    def _initialize_cells(self):
        max_column_name_width = max(len(col) for col in self.df.get_header())
        self.cells[:] = [
            CsvCell(
                df=self.df,
                row_index=self.row_index,
                name=name,
                max_column_name_width=max_column_name_width,
            )
            for name, _ in self.df.get_row_dict(self.row_index).items()
        ]

    def on_enter_pressed(self):
        self.edit_cell()

    def edit_cell(self, external_editor=False):
        cell = self.get_selected_item()
        if cell is not None:
            value = self.df.get_cell(self.row_index, cell.name)

            if external_editor:
                new_value = edit_text(text=value).rstrip()
            else:
                new_value = InputMenu(
                    prompt=f"edit {cell.name}",
                    text=value,
                    items=self.df.get_unique_values_for_column(cell.name),
                ).request_input()

            if new_value is not None and new_value != value:
                self.df.set_cell(self.row_index, cell.name, new_value)
                self.df.save_csv()
                # If the header is changed, close the menu because the cell becomes invalid.
                if self.row_index == 0:
                    self.close()
                self.update_screen()


def _get_setting_file(csv_file: str) -> str:
    tmp_dir = os.path.join(os.path.dirname(csv_file), "tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    return os.path.join(tmp_dir, "csvmenu_setting.json")


class CsvMenu(Menu[CsvRow]):
    def __init__(self, csv_file: str, text: str = ""):
        self.__setting_file = _get_setting_file(csv_file)
        self.__settings = load_json(self.__setting_file, default={})

        self.df = CsvData(csv_file)
        self.selected_val: Optional[str] = None

        self._rows: List[CsvRow] = []
        self.__update_rows()

        self._select_row = False

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
        self.add_command(self.__sort_by_column, hotkey="alt+s")

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

    def __update_rows(self):
        self._rows.clear()
        for row_index in range(self.df.get_row_count()):
            self._rows.append(CsvRow(df=self.df, row_index=row_index))

    def on_enter_pressed(self):
        if self._select_row:
            super().on_enter_pressed()
        else:
            row = self.get_selected_item()
            if row is not None:
                self.__edit_row(row_index=row.row_index)

    def __edit_row(self, row_index: int):
        menu = RowMenu(df=self.df, row_index=row_index)
        menu.exec()
        if menu.selected_cell is not None:
            val = self.df.get_cell(row_index, menu.selected_cell.name)
            self.selected_val = val
            self.close()

    def get_item_text(self, item: CsvRow) -> str:
        row = self.df.get_row_list(item.row_index)
        s = COLUMN_SEPARATOR.join(
            [
                format_text(
                    text,
                    column_width=self.df.column_width[i],
                    row_index=item.row_index,
                    is_last_column=i == len(row) - 1,
                )
                for i, text in enumerate(map(str, row))
            ]
        )
        return s

    def __add_column(self):
        name = InputMenu(prompt="New column name").request_input()
        if name is not None and name != "":
            self.df.add_column(name=name)
            self.df.save_csv()
            self.__update_rows()
            self.set_message(f'added column "{name}"')

    def __add_row(self, row_index=None):
        row_index = self.df.add_row(index=row_index)
        self.__update_rows()
        self.__edit_row(row_index=row_index)
        self.set_selected_row(row_index)

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
            self.__update_rows()
            self.set_selected_row(dup_row_index)
            self.__edit_row(dup_row_index)

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
