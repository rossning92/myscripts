import logging
import os
import platform
import re
import shutil
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Optional

from _shutil import convert_to_unix_path, is_in_wsl

from utils.jsonutil import load_json, save_json


@dataclass
class ScriptDirectory:
    name: str
    path: str  # absolute path of script directory
    glob: Optional[str] = None  # glob pattern to match files in this directory


@lru_cache(maxsize=None)
def get_script_dirs_config_file():
    config_json_file = os.path.join(get_data_dir(), "script_directories.json")
    return config_json_file


@lru_cache(maxsize=None)
def get_script_directories() -> List[ScriptDirectory]:
    directories: List[ScriptDirectory] = []

    # Scripts root dir
    directories.append(
        ScriptDirectory(
            name="",
            path=os.path.join(get_my_script_root(), "scripts"),
        )
    )

    # Settings dir
    directories.append(
        ScriptDirectory(
            name="settings",
            path=os.path.join(get_my_script_root(), "settings"),
            glob="*",
        )
    )

    # libs dir
    directories.append(
        ScriptDirectory(
            name="libs",
            path=os.path.join(get_my_script_root(), "libs"),
        )
    )

    config_file = get_script_dirs_config_file()
    data = load_json(config_file, default=[])

    for item in data:
        name = item["name"]

        directory = item["directory"]
        if is_in_wsl():
            directory = convert_to_unix_path(directory, wsl=True)

        if not os.path.isabs(directory):  # is relative path
            directory = os.path.abspath(
                os.path.join(
                    # Relative to "script_directories.json" config file
                    os.path.dirname(config_file),
                    directory,
                )
            )

        if not os.path.isdir(directory):
            logging.warning(f"Script directory does not exist, skipping: {directory}")
            continue

        directories.append(ScriptDirectory(name=name, path=directory))

    return directories


@lru_cache(maxsize=None)
def get_script_root() -> str:
    # Reversely enumerate the script directories in case the user overrides the
    # default script directory root.
    for d in reversed(get_script_directories()):
        if d.name == "":
            logging.debug(f"Script root: {d.path}")
            return d.path

    raise Exception("Failed to find script root directory.")


@lru_cache(maxsize=None)
def get_my_script_root():
    return os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + "/../../../")


@lru_cache(maxsize=None)
def get_data_dir() -> str:
    data_dir_config_file = os.path.abspath(
        os.path.join(get_my_script_root(), "config", "data_dir.txt")
    )
    if os.path.exists(data_dir_config_file):
        with open(data_dir_config_file, "r") as f:
            data_dir = f.read().strip()
            if not os.path.isabs(data_dir):  # if relative path
                data_dir = os.path.normpath(
                    os.path.join(
                        get_my_script_root(), data_dir.replace("/", os.path.sep)
                    )
                )

    else:
        data_dir = os.path.abspath(
            "%s/tmp/data/%s" % (get_my_script_root(), platform.node())
        )
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def get_script_history_file():
    return os.path.join(os.path.join(get_data_dir(), "last_script.json"))


def get_bin_dir():
    return os.path.join(get_my_script_root(), "bin")


@lru_cache(maxsize=None)
def get_variable_edit_history_file():
    return os.path.join(get_data_dir(), "variable_edit_history.json")


@lru_cache(maxsize=None)
def get_variable_file() -> str:
    variable_file_v2 = os.path.join(get_data_dir(), "variables_v2.json")

    # TODO: migrate to new variable file
    if True:
        if not os.path.exists(variable_file_v2):
            variable_file_v1 = os.path.join(get_data_dir(), "variables.json")
            if os.path.exists(variable_file_v1):
                shutil.copy(variable_file_v1, get_variable_edit_history_file())

                variables = load_json(variable_file_v1)
                variables_v2 = {k: v[0] for k, v in variables.items()}
                save_json(variable_file_v2, variables_v2)

    return variable_file_v2


def get_script_config_file_path(script_path: str) -> str:
    return os.path.splitext(script_path)[0] + ".config.json"


def get_default_script_config_path(script_path: str) -> str:
    return os.path.join(os.path.dirname(script_path), ".default.config.json")


def get_script_config_file(script_path: str) -> Optional[str]:
    f = get_script_config_file_path(script_path)
    if os.path.exists(f):
        return f

    return None


@lru_cache(maxsize=None)
def get_temp_dir() -> str:
    temp_dir = os.path.join(tempfile.gettempdir(), "myscripts")
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir


def get_relative_script_path(path: str) -> str:
    path = path.replace("\\", "/")
    for d in get_script_directories():
        prefix = d.path.replace("\\", "/") + "/"
        if path.startswith(prefix):
            path = (d.name + "/" if d.name else "") + path[len(prefix) :]
            break
    return path


def get_absolute_script_path(path: str):
    # If already absolute path
    if os.path.isabs(path):
        return path

    script_dirs = get_script_directories()
    path_arr = path.split("/")
    if path_arr:
        if path_arr[0] == "r" or path_arr[0] == "ext":
            path_arr.insert(0, os.path.join(get_my_script_root(), "scripts"))
        else:
            matched_script_dir = next(
                filter(lambda d: d.name == path_arr[0], script_dirs), None
            )
            if matched_script_dir:
                path_arr[0] = matched_script_dir.path
            else:
                path_arr.insert(0, get_script_root())
    return os.path.join(*path_arr)


def get_script_alias(name_without_ext: str) -> str:
    basename = os.path.basename(name_without_ext)
    if basename:
        words = re.split("[^a-zA-Z0-9]+", basename)
        if 1 <= len(words) <= 4:
            return "".join((w[0].lower() if w else "" for w in words))
        else:
            return ""
    else:
        return ""
