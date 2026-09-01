import glob
import os
import shutil
from datetime import datetime
from typing import Iterator, List

MAX_HISTORY = 100


class HistoryManager:
    def __init__(
        self,
        save_dir: str,
        prefix: str,
        ext: str,
        max_history=MAX_HISTORY,
        directory: bool = False,
    ) -> None:
        self.__max_history = max_history
        self.__save_dir = save_dir
        self.__prefix = prefix
        self.__ext = ext
        self.__directory = directory

    def get_all_files(self) -> List[str]:
        files = glob.glob(
            os.path.join(self.__save_dir, f"{self.__prefix}*{self.__ext}")
        )
        if self.__directory:
            files = [file for file in files if os.path.isdir(file)]
        return sorted(files, key=os.path.getmtime)

    def get_all_files_desc(self) -> Iterator[str]:
        return reversed(self.get_all_files())

    def delete_old_files(self):
        files = self.get_all_files()
        for file in files[: max(0, len(files) - self.__max_history)]:
            if self.__directory:
                shutil.rmtree(file)
            else:
                os.remove(file)

    def get_new_file(self):
        os.makedirs(self.__save_dir, exist_ok=True)
        dt = datetime.now().strftime("%y%m%d%H%M%S")
        return os.path.join(
            self.__save_dir,
            f"{self.__prefix}{dt}{self.__ext}",
        )

    def create_new_file(self) -> str:
        file = self.get_new_file()
        if self.__directory:
            os.makedirs(file, exist_ok=True)
        else:
            open(file, "a").close()
        self.delete_old_files()
        return file
