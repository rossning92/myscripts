import json
import logging
import os
import re
import shutil
import subprocess
from typing import Any, Callable, Dict, Generator, List, Literal, Optional, Tuple

from _pkgmanager import require_package
from _script import (
    Script,
    _load_script_config_file,
    _save_script_config_file,
    get_all_scripts,
    get_default_script_config,
)
from _shutil import quote_arg
from utils.clip import set_clip_osc52
from utils.editor import is_vscode_available, open_in_vscode
from utils.jsonutil import save_json
from utils.menu import Menu
from utils.menu.dicteditmenu import DictEditMenu
from utils.script.path import (
    get_absolute_script_path,
    get_data_dir,
    get_my_script_root,
    get_relative_script_path,
    get_script_config_file,
    get_script_config_file_path,
    get_script_directories,
    get_script_root,
)
from utils.template import render_template_file
from utils.tmux import is_in_tmux

SCRIPT_ROOT = os.path.dirname(os.path.abspath(__file__))


def get_selected_script_path_rel(script_path=None) -> Optional[str]:
    if script_path is None:
        script_path = os.getenv("SCRIPT")
        if not script_path:
            return None
    rel_path = script_path.replace(get_script_root() + os.path.sep, "")
    rel_path = rel_path.replace("\\", "/")
    return rel_path


def get_selected_script_dir_rel(script_path=None) -> Optional[str]:
    rel_path = get_selected_script_path_rel(script_path=script_path)
    if not rel_path:
        return None
    rel_path = os.path.dirname(rel_path)
    if rel_path:
        rel_path += "/"
    return rel_path


def create_myscript_workspace() -> str:
    # Create a VSCode workspace to work with all scripts together.
    script_root = get_my_script_root()
    folders = [
        {
            "path": script_root,
        }
    ]
    folders.extend(
        [
            {"path": d.path}
            for d in get_script_directories()
            if script_root not in d.path
        ]
    )
    folders.sort(
        # HACK: Foam directory must be first in order for [[wikilinks]] to work.
        key=lambda item: 0 if os.path.exists(os.path.join(item["path"], ".foam")) else 1
    )
    workspace_file = os.path.join(get_data_dir(), "myscripts.code-workspace")
    save_json(
        workspace_file,
        {"folders": folders, "settings": {"search.exclude": {"**/.config": True}}},
    )
    return workspace_file


def open_myscript_workspace():
    workspace_file = create_myscript_workspace()
    open_in_vscode([workspace_file])


def edit_script(
    file: str, editor: Literal["auto", "vim", "vscode"] = "auto", line: int = None
):
    if os.path.splitext(file)[1] == ".link":
        file = open(file, "r", encoding="utf-8").read().strip()

    use_vscode = editor == "vscode" or (
        editor == "auto" and is_vscode_available() and not is_in_tmux()
    )
    if use_vscode:
        workspace_file = create_myscript_workspace()
        open_in_vscode([workspace_file, file], line_number=line)
    else:
        require_package("neovim")

        args = ["nvim"]
        if line is not None:
            args.append(f"+{line}")
        args.append(file)
        subprocess.run(args)


def enter_script_path():
    script_rel_path = get_selected_script_dir_rel()
    if not script_rel_path:
        return None
    script_dir = script_rel_path.lstrip("/")
    script_path = input("Script path (%s [Enter]): " % script_dir)
    if not script_path:
        script_name = input("Script path %s" % script_dir)
        if not script_name:
            return ""

        script_path = script_dir + script_name

    # Check if new script should be saved in script directories
    script_dirs = get_script_directories()
    separated_path = script_path.split("/")
    if separated_path:
        matched_script_dir = next(
            filter(lambda x: x.name == separated_path[0], script_dirs), None
        )
        if matched_script_dir:
            separated_path[0] = matched_script_dir.path
    script_path = "/".join(separated_path)

    return script_path


def edit_script_config(script_path: str):
    default_config = get_default_script_config()

    script_config_file = get_script_config_file(script_path)
    if script_config_file is None:
        data = {}
    else:
        data = _load_script_config_file(script_config_file)

    data = {**default_config, **data}

    script_config_file_path = get_script_config_file_path(script_path)

    def on_dict_update(dict):
        data = {k: v for k, v in dict.items() if default_config[k] != v}
        _save_script_config_file(
            data,
            script_config_file_path,
        )

    config_edit_history_file = os.path.join(get_data_dir(), "config_edit_history.json")
    if os.path.exists(config_edit_history_file):
        with open(config_edit_history_file, "r") as f:
            config_edit_history = json.load(f)
    else:
        config_edit_history = {}

    def on_dict_history_update(config_edit_history: Dict[str, List[Any]]):
        with open(config_edit_history_file, "w", encoding="utf-8") as f:
            json.dump(config_edit_history, f, indent=2)

    script_config_file_rel_path = get_relative_script_path(script_config_file_path)
    w = DictEditMenu(
        data,
        default_dict=default_config,
        on_dict_update=on_dict_update,
        prompt=f"edit setting ({script_config_file_rel_path})",
        on_dict_history_update=on_dict_history_update,
        dict_history=config_edit_history,
    )
    ret = w.exec()
    if ret == -1:
        return False
    else:
        return True


def copy_script_path_to_clipboard(
    script: Script, with_variables=False, format="cmdline"
):
    script_path = script.script_path
    _, ext = os.path.splitext(script_path)

    if script_path.endswith(".user.js"):
        url = script.get_userscript_url()
        set_clip_osc52(url)
        logging.info("Copied url: %s" % url)

    elif ext == ".md" or ext == ".txt":
        with open(script_path, "r", encoding="utf-8") as f:
            set_clip_osc52(f.read())
        logging.info("copied")

    else:
        # Convert to relative path
        script_path = get_relative_script_path(script_path)
        if " " in script_path:  # quote  path if it contains spaces
            script_path = '"' + script_path + '"'

        variables = script.get_variables() if with_variables else {}
        variables.pop("MYSCRIPT_ROOT", None)

        if format == "cmdline":
            content = ""
            for k, v in variables.items():
                if v:
                    content += "%s=%s " % (k, quote_arg(v, shell_type="bash"))

            content += f"run_script {script_path}"
        elif format == "include":
            if variables:
                content = "{{ include('%s', %s) }}" % (
                    script_path,
                    variables,
                )
            else:
                content = "{{ include('%s') }}" % (script_path)
        else:
            raise Exception(f'Invalid format specified "{format}".')

        set_clip_osc52(content)
        return content


def create_new_script(
    src_script_path: Optional[str] = None,
    script_dirs: Optional[List[str]] = None,
    duplicate=False,
) -> Optional[str]:
    label: str
    src_script_rel_path = get_selected_script_path_rel(script_path=src_script_path)

    if not src_script_rel_path:
        return None if duplicate else ""

    text = (
        src_script_rel_path if duplicate else os.path.dirname(src_script_rel_path) + "/"
    )
    label = "duplicate script" if duplicate else "new script"

    w: Menu = Menu(prompt=label, text=text, items=script_dirs)
    w.exec()
    dest_script = w.get_text()
    if not dest_script:
        return None

    # Convert to abspath
    dest_script = get_absolute_script_path(dest_script)
    dest_script_config_file = get_script_config_file_path(dest_script)

    dir_name = os.path.dirname(dest_script)
    if dir_name != "":
        os.makedirs(dir_name, exist_ok=True)

    # Check script extensions
    name_without_ext, ext = os.path.splitext(dest_script)
    if not ext:
        logging.warning("Script extension is required.")

    if duplicate:
        assert src_script_path is not None
        if not os.path.isabs(src_script_path):
            src_script = os.path.join(get_script_root(), src_script_path)
        else:
            src_script = src_script_path
        shutil.copyfile(src_script, dest_script)
        src_script_config_file = get_script_config_file(src_script)
        if src_script_config_file is not None:
            shutil.copyfile(src_script_config_file, dest_script_config_file)

    else:
        template_root = os.path.join(get_my_script_root(), "templates")
        if ext == ".py":
            shutil.copyfile(os.path.join(template_root, "python.py"), dest_script)
        elif ext == ".mmd":
            shutil.copyfile(os.path.join(template_root, "mermaid.mmd"), dest_script)
        elif ext == ".glsl":
            shutil.copyfile(os.path.join(template_root, "shader.glsl"), dest_script)
        elif ext == ".png":
            # Create an excalidraw png file
            dest_script = name_without_ext + ".excalidraw.png"
            with open(dest_script, "w") as _:
                pass
        elif dest_script.endswith(".user.js"):
            userscript_name = re.sub(r"\.user\.js$", "", os.path.basename(dest_script))
            render_template_file(
                os.path.join(get_my_script_root(), "templates", "userscript.user.js"),
                dest_script,
                context={
                    "USERSCRIPT_NAME": userscript_name,
                    "USERSCRIPT_LIB": "http://127.0.0.1:4312/userscriptlib.js",
                },
            )
        else:
            # Create empty file
            with open(dest_script, "w") as _:
                pass

    edit_script(os.path.realpath(dest_script))
    return dest_script


def replace_script_str(
    old: str,
    new: Optional[str] = None,
    dry_run: bool = False,
    matched_files: Optional[List[str]] = None,
    files_to_replace: Optional[List[str]] = None,
    on_progress: Optional[Callable[[str], bool]] = None,
) -> Generator[Tuple[str, int, str], None, None]:
    if files_to_replace is None:
        files_to_replace = list(get_all_scripts())

    for i, file in enumerate(files_to_replace):
        if on_progress is not None:
            if i % 20 == 0:
                if on_progress("searching (%d/%d)" % (i + 1, len(files_to_replace))):
                    break

        try:
            with open(file, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
        except UnicodeDecodeError:
            # Ignore non-text files.
            continue

        dirty = False
        for j, line in enumerate(lines):
            if old in line:
                if dry_run:
                    yield (get_relative_script_path(file), j + 1, lines[j])
                elif new is not None:
                    lines[j] = line.replace(old, new)
                else:
                    raise Exception("Replacement string cannot be empty")
                dirty = True

        if dirty:
            if matched_files is not None:
                matched_files.append(file)
            if not dry_run:
                logging.debug(f"Replace in file: {file}: `{old}` -> `{new}`")
                s = "\n".join(lines)
                with open(file, "w", encoding="utf-8") as f:
                    f.write(s)


def rename_script(
    script_full_path,
    replace_all_occurrence: bool = False,
) -> Optional[str]:
    script_rel_path = get_relative_script_path(script_full_path)

    items: List[str] = []
    menu = Menu(
        prompt="rename script", search_mode=False, text=script_rel_path, items=items
    )

    def on_progress(message: str) -> bool:
        menu.set_message(message)
        ret = menu.process_events()
        if ret:
            menu.set_message("search canceled")
        return ret

    matched_files: List[str] = []
    with menu:
        if replace_all_occurrence:
            for line in replace_script_str(
                script_rel_path,
                dry_run=True,
                matched_files=matched_files,
                on_progress=on_progress,
            ):
                items.append(f"{line[0]}:{line[1]}:\t{line[2]}")

    menu.set_message("search completed")
    menu.exec()

    # Get new script path
    new_script_rel_path = menu.get_text()
    if not new_script_rel_path:
        return None

    # Rename script
    new_script_full_path = get_absolute_script_path(new_script_rel_path)
    if os.path.abspath(new_script_full_path) == os.path.abspath(script_full_path):
        return None
    if os.path.lexists(new_script_full_path):
        raise FileExistsError(f'Path already exists: "{new_script_rel_path}"')
    os.makedirs(os.path.dirname(new_script_full_path), exist_ok=True)
    shutil.move(script_full_path, new_script_full_path)

    # Rename config file if any
    config_file = get_script_config_file_path(script_full_path)
    new_config_file = get_script_config_file_path(new_script_full_path)
    if os.path.exists(config_file):
        shutil.move(config_file, new_config_file)

    # Replace script string
    if replace_all_occurrence:
        list(
            replace_script_str(
                script_rel_path, new_script_rel_path, files_to_replace=matched_files
            )
        )
    return new_script_full_path
