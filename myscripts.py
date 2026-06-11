# ruff: noqa: E402

import argparse
import hashlib
import io
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
from typing import Any, Dict, List, Optional

MYSCRIPT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(MYSCRIPT_ROOT, "libs"))
sys.path.append(os.path.join(MYSCRIPT_ROOT, "bin"))
sys.path.append(os.path.join(MYSCRIPT_ROOT, "scripts"))
sys.path.append(os.path.join(MYSCRIPT_ROOT, "scripts", "r"))

from _ext import (
    copy_script_path_to_clipboard,
    create_new_script,
    edit_script,
    edit_script_config,
    rename_script,
)
from _script import (
    Script,
    get_default_script_config,
    get_script_variables,
    is_instance_running,
    setup_env_var,
    try_reload_scripts_autorun,
    update_variables,
)
from _scriptmanager import ScriptManager, execute_script
from _scriptserver import ScriptServer
from _shutil import (
    append_to_path_global,
    quote_arg,
    refresh_env_vars,
    run_at_startup,
    setup_nodejs,
)
from utils.clip import set_clip_osc52
from utils.fileutils import read_last_line
from utils.jsonutil import load_json, save_json
from utils.logger import setup_logger
from utils.menu import Menu
from utils.menu.confirmmenu import confirm
from utils.menu.dicteditmenu import DictEditMenu
from utils.menu.exceptionmenu import ExceptionMenu
from utils.menu.filemenu import FileMenu
from utils.menu.inputmenu import InputMenu
from utils.menu.logmenu import LogMenu
from utils.platform import is_termux
from utils.script.path import (
    get_data_dir,
    get_script_config_file_path,
    get_variable_edit_history_file,
)
from utils.term import hide_terminal_from_taskbar, set_terminal_title
from utils.timeutil import time_diff_str
from utils.tmux import has_tmux_session, is_in_tmux

_REFRESH_INTERVAL_SECS = 60


script_server: Optional[ScriptServer] = None


def format_key_value_pairs(kvp):
    result = []
    key_length = [len(key) for key in kvp]
    if key_length:
        max_key_length = max(key_length) + 1
    else:
        max_key_length = 0
    for key, value in kvp.items():
        result.append(key.ljust(max_key_length) + ": " + value)
    return result


def format_variables(variables, variable_names, variable_prefix) -> List[str]:
    result = []
    short_var_names = [
        re.sub("^" + re.escape(variable_prefix), "", x) for x in variable_names
    ]
    for full_name, short_name in zip(variable_names, short_var_names):
        var_val = variables.get(full_name, "")
        result.append(f"var: {short_name:<16} : {var_val}")
    return result


class EditVariableMenu(DictEditMenu):
    def __init__(self, script: Script):
        self.variables = get_script_variables(script)
        self.variable_edit_history = load_json(get_variable_edit_history_file(), {})
        super().__init__(
            self.variables,
            prompt=f"{script.name} > edit vars",
            on_dict_update=self.on_dict_update,
            on_dict_history_update=self.on_dict_history_update,
            dict_history=self.variable_edit_history,
        )

        self.add_command(self.__clear_value, hotkey="delete")
        self.add_command(self.__clear_value, hotkey="ctrl+k")
        self.add_command(self.__select_directory, hotkey="alt+d")
        self.add_command(self.__select_file, hotkey="alt+f")

    def on_dict_history_update(self, history: Dict[str, List[Any]]):
        save_json(get_variable_edit_history_file(), history)

    def __clear_value(self):
        key = self.get_selected_key()
        if key is not None:
            self.set_dict_value(key, "")

    def __select_directory(self):
        key = self.get_selected_key()
        if key is not None:
            dir_path = FileMenu(goto=self.get_value(key)).select_directory()
            if dir_path is not None:
                self.set_dict_value(key, dir_path)

    def __select_file(self):
        key = self.get_selected_key()
        if key is not None:
            file_path = FileMenu(goto=self.get_value(key)).select_file()
            if file_path is not None:
                self.set_dict_value(key, file_path)

    def on_dict_update(self, d: Dict):
        update_variables(d)


def restart_program():
    if script_server is not None:
        script_server.stop_server()

    for t in threading.enumerate():
        if t is not threading.main_thread():
            logging.debug(f"Waiting {t} to exit...")
            t.join()

    os.execl(
        sys.executable,
        sys.executable,
        *(x for x in sys.argv if x != "--startup"),
    )


class _ScheduledScript:
    def __init__(self, script: Script, scheduled_time: float) -> None:
        self.script = script
        self.scheduled_time = scheduled_time

    def __str__(self) -> str:
        script_log_file = self.script.get_script_log_file()
        if os.path.exists(script_log_file):
            last_line = read_last_line(script_log_file)
        else:
            last_line = None

        return f"{time_diff_str(self.scheduled_time):<4} : {os.path.basename(self.script.script_path)} : {last_line}"


class _ScheduledScriptMenu(Menu[_ScheduledScript]):
    def __init__(self, script_manager: ScriptManager):
        items = [
            _ScheduledScript(script=script, scheduled_time=scheduled_time)
            for script, scheduled_time in script_manager.get_scheduled_scripts_run_time().items()
        ]
        super().__init__(items=items, prompt="scheduled scripts")

    def on_idle(self):
        self.update_screen()
        return super().on_idle()

    def on_enter_pressed(self):
        item = self.get_selected_item()
        if item is not None:
            script_log_file = item.script.get_script_log_file()
            if os.path.exists(script_log_file):
                LogMenu(files=[script_log_file]).exec()


def get_scheduled_script_logs(script_manager: ScriptManager) -> List[str]:
    logs: List[str] = []
    for (
        script,
        scheduled_time,
    ) in script_manager.get_scheduled_scripts_run_time().items():
        script_log_file = script.get_script_log_file()
        if os.path.exists(script_log_file):
            last_line = read_last_line(script_log_file)
            logs.append(
                f"sched: {time_diff_str(scheduled_time):<4} : {os.path.basename(script.script_path)} : {last_line.strip()}"
            )
    return logs


class _MyScriptMenu(Menu[Script]):
    def __init__(
        self,
        script_manager: ScriptManager,
        no_daemon=False,
        run_script_and_quit=False,
        input_text: Optional[str] = None,
        cmdline_args: Optional[List[str]] = None,
        out_to_file: Optional[str] = None,
        prompt: Optional[str] = None,
    ):
        self.script_manager = script_manager
        self.__no_daemon = no_daemon
        self.last_refresh_time = 0.0
        self.is_refreshing = False
        self.__run_script_and_quit = run_script_and_quit
        self.__cmdline_args: List[str] = cmdline_args if cmdline_args else []
        self.__auto_infer_cmdline_args: bool = not bool(cmdline_args)
        self.__last_copy_time = 0.0
        self.__last_keyboard_interrupt_time = 0.0
        self.__filemgr = FileMenu()
        self.__out_to_file = out_to_file

        super().__init__(
            items=self.script_manager.scripts,
            ascii_only=False,
            cancellable=run_script_and_quit,
            prompt=prompt if prompt else platform.node() + "$",
            prompt_color=(
                "black",
                ["red", "green", "yellow", "blue", "magenta", "cyan"][
                    int(hashlib.md5(platform.node().encode()).hexdigest(), 16) % 6
                ],
            ),
            text=input_text,
        )

        self.add_command(self._copy_cmdline, hotkey="ctrl+y")
        self.add_command(self._copy_to)
        self.add_command(self._copy_file_path, hotkey="alt+y")
        self.add_command(self._delete_file, hotkey="ctrl+k")
        self.add_command(self._duplicate_script, hotkey="ctrl+d")
        self.add_command(self._edit_script_settings, hotkey="ctrl+s")
        self.add_command(self._new_script, hotkey="ctrl+n")
        self.add_command(self._list_scheduled_scripts)
        self.add_command(self._run_script_no_close, hotkey="alt+enter")
        self.add_command(self._run_script_no_close, hotkey="ctrl+enter")
        self.add_command(self._run_script_local)
        self.add_command(self._run_script_background)
        self.add_command(self._reload_scripts, hotkey="ctrl+r")
        self.add_command(self._reload, hotkey="alt+r")
        self.add_command(self._rename_script, hotkey="alt+n")
        self.add_command(self._rename_script_replace_all)
        self.add_command(self._set_cmdline_args, hotkey="alt+a")

    def _reload(self):
        self.run_raw(lambda: restart_program())

    def _list_scheduled_scripts(self):
        _ScheduledScriptMenu(script_manager=self.script_manager).exec()

    def _set_cmdline_args(self):
        script = self.get_selected_script()
        if script:
            input = InputMenu(prompt="args").request_input()
            if input is not None:
                self.__cmdline_args[:] = [input]

    def _delete_file(self):
        script = self.get_selected_script()

        if script and confirm(f'Delete "{script.script_path}"?', prompt_color="red"):
            os.remove(script.script_path)

            script_config_path = get_script_config_file_path(script.script_path)
            if os.path.exists(script_config_path):
                os.remove(script_config_path)

            self.script_manager.scripts.remove(script)

    def _execute_script_background(self, script: Script):
        script.execute(
            args=[],
            close_on_exit=True,
            restart_instance=False,
            new_window=False,
            background=True,
        )

    def _run_script_background(self):
        script = self.get_selected_script()
        if script:
            self.run_raw(lambda: self._execute_script_background(script))

    def on_main_loop(self):
        # Reload scripts
        now = time.time()
        if (
            now - self.last_key_pressed_timestamp > _REFRESH_INTERVAL_SECS
            and now - self.last_refresh_time > _REFRESH_INTERVAL_SECS
        ):
            self._reload_scripts()

        for script in self.script_manager.get_scheduled_scripts_to_run():
            try:
                self.run_raw(
                    lambda script=script: self._execute_script_background(script)
                )
            except Exception as ex:
                logging.error(f"Error on running scheduled script: {ex}")

    def match_item(self, keyword: str, script: Script, index: int) -> int:
        if len(keyword) > 0 and script.alias == keyword:
            return 2
        else:
            if script.match_pattern(keyword):
                return 1
            else:
                return super().match_item(patt=keyword, item=script, index=index)

    def get_item_metadata(self, script: Script) -> str:
        return f"<file><path>{script.script_path}</path></file>"

    def _run_selected_script(self, close_on_exit=None, run_script_local=False):
        try:
            script = self.get_selected_item()
            if script:
                script.update_script_access_time()
                self.script_manager.sort_scripts()
                self.refresh()

                self.run_raw(
                    lambda: execute_script(
                        script,
                        args=self.__cmdline_args if self.__cmdline_args else None,
                        cd=len(self.__cmdline_args) == 0
                        and not self.__run_script_and_quit,
                        close_on_exit=close_on_exit,
                        out_to_file=self.__out_to_file,
                        run_script_and_quit=self.__run_script_and_quit,
                        run_script_local=run_script_local,
                    )
                )

                if self.__run_script_and_quit:
                    self.close()
                    return

                if script.cfg["reloadScriptsAfterRun"]:
                    logging.info("Reload scripts after running: %s" % script.name)
                    self._reload_scripts()

                self.clear_input(reset_selection=True)

        except Exception:
            output = io.StringIO()
            traceback.print_exc(file=output)
            err_lines = output.getvalue().splitlines()
            Menu(prompt="Error on run_selected_script", items=err_lines).exec()

        finally:
            # Reset the last refresh time whenever we run a script.
            self.update_last_refresh_time()

            # Make sure to recover the original terminal title in case it's being modified by other programs.
            set_terminal_title("myscriptsmgr")

    def get_selected_script(self) -> Optional[Script]:
        index = self.get_selected_index()
        if index >= 0:
            return self.items[index]
        else:
            return None

    def get_selected_script_path(self) -> Optional[str]:
        script = self.get_selected_item()
        if script is not None:
            return script.script_path
        else:
            return None

    def _on_register_hotkeys(self, hotkeys: Dict[str, Script]):
        self.delete_commands_if(lambda cmd: cmd.name.startswith("run: "))
        for hotkey, script in hotkeys.items():
            self.add_command(
                lambda script=script: self._run_hotkey(script),
                hotkey=hotkey,
                name="run: " + script.name,
            )

    def _reload_scripts(self):
        if self.is_refreshing:
            return

        self.is_refreshing = True
        self.set_message("reloading script")

        def on_progress(i: int):
            nonlocal self
            self.process_events()
            self.set_message(f"reloading script: {i + 1}")

        self.script_manager.refresh_all_scripts(
            on_progress=on_progress, on_register_hotkeys=self._on_register_hotkeys
        )
        self.set_message("scripts reloaded")
        self.update_last_refresh_time()
        self.is_refreshing = False

        if self.__run_script_and_quit:
            self.refresh()
            if self.get_row_count() == 1:
                self._run_selected_script()

        return True

    def _edit_script_settings(self):
        script = self.get_selected_script()
        if script:
            edit_script_config(script.script_path)
            script.refresh_script()

    def _copy_cmdline(self):
        script = self.get_selected_script()
        if script:
            now = time.time()
            include_derivative = now < self.__last_copy_time + 1
            content = copy_script_path_to_clipboard(
                script,
                format="include" if include_derivative else "cmdline",
                with_variables=include_derivative,
            )
            self.set_message(f"copied: {content}" if content else "copied")
            self.__last_copy_time = now

    def _copy_to(self):
        script = self.get_selected_script()
        if script:
            script_path = script.get_script_path()
            self.__filemgr.copy_to(script_path)

    def _copy_file_path(self):
        script = self.get_selected_script()
        if script:
            script_path = script.get_script_path()
            set_clip_osc52(script_path)
            self.set_message(f"copied: {script_path}")

    def _new_script_or_duplicate_script(
        self, src_script_path: Optional[str], duplicate=False
    ):
        script_dirs = sorted(
            set(os.path.dirname(x.name) + "/" for x in self.script_manager.scripts)
        )
        script_path = create_new_script(
            src_script_path=src_script_path,
            script_dirs=script_dirs,
            duplicate=duplicate,
        )
        if script_path:
            script = Script(script_path)
            self.script_manager.scripts.insert(0, script)
        self.clear_input()

    def _new_script(self):
        src_script_path = self.get_selected_script_path()
        self._new_script_or_duplicate_script(src_script_path=src_script_path)

    def _duplicate_script(self):
        src_script_path = self.get_selected_script_path()
        if src_script_path:
            self._new_script_or_duplicate_script(
                src_script_path=src_script_path, duplicate=True
            )

    def _rename_script(self, replace_all_occurrence=False):
        script = self.get_selected_script()
        if script:
            new_script_path = rename_script(
                script.script_path,
                replace_all_occurrence=replace_all_occurrence,
            )
            if new_script_path:
                index = self.script_manager.scripts.index(script)
                new_script = Script(new_script_path)
                self.script_manager.scripts[index] = new_script

        self.clear_input()

    def _rename_script_replace_all(self):
        self._rename_script(
            replace_all_occurrence=True,
        )

    def _edit_script(self):
        script_path = self.get_selected_script_path()
        if script_path:
            self.run_raw(lambda: edit_script(script_path))

    def _edit_script_vim(self):
        script_path = self.get_selected_script_path()
        if script_path:
            self.run_raw(lambda: edit_script(script_path, editor="vim"))

    def update_last_refresh_time(self):
        self.last_refresh_time = time.time()

    def _run_script_no_close(self):
        self._run_selected_script(close_on_exit=False)

    def _run_script_local(self):
        self._run_selected_script(run_script_local=True)

    def on_char(self, ch):
        self.set_message(None)

        try:
            if ch == "\t":
                script = self.get_selected_item()
                if script is not None:
                    w = EditVariableMenu(script)
                    if len(w.variables) > 0:
                        w.exec()
                return True
            else:
                return super().on_char(ch)
        finally:
            # Reset last refresh time when key press event is processed
            self.update_last_refresh_time()

    def on_keyboard_interrupt(self):
        if is_in_tmux():
            subprocess.check_call(["tmux", "detach-client"])
        else:
            now = time.time()
            self.set_message("press ctrl+c again to exit")
            if now < self.__last_keyboard_interrupt_time + 1:
                self.close()
            self.__last_keyboard_interrupt_time = now

    def on_enter_pressed(self):
        self._run_selected_script()
        return True

    def on_idle(self):
        try_reload_scripts_autorun(self.script_manager.scripts_autorun)

    def on_item_selection_changed(self, script: Optional[Script], i: int):
        if self.__auto_infer_cmdline_args:
            text = self.get_input()
            if script and text:
                match = script.match_pattern(text)
                if match:
                    self.__cmdline_args[:] = [match.group()]
                else:
                    self.__cmdline_args.clear()
            else:
                self.__cmdline_args.clear()

    def get_status_text(self) -> str:
        if not self.is_refreshing:
            lines: List[str] = []

            script = self.get_selected_item()
            if script is not None:
                default_script_config = get_default_script_config()

                # Command line args
                if self.__cmdline_args:
                    lines.append((f"[arg] {self.__cmdline_args}"))

                # Variables
                try:
                    vars = get_script_variables(script)
                    if len(vars) > 0:
                        lines.extend(
                            [
                                x
                                for x in format_variables(
                                    vars,
                                    sorted(script.get_variable_names()),
                                    script.get_public_variable_prefix(),
                                )
                            ]
                        )
                except Exception as e:
                    logging.error(f"Error on script: {script.script_path}: {e}")

                # Script configs
                for name, value in script.cfg.items():
                    if value != default_script_config[name]:
                        lines.append(f"cfg: {name:<16} : {value}")

            # Scheduled script logs
            if not self.__no_daemon:
                lines.extend(
                    [line for line in get_scheduled_script_logs(self.script_manager)]
                )
            return "\n".join(lines) + "\n" + super().get_status_text()
        else:
            return super().get_status_text()

    def _run_hotkey(self, script: Script):
        if is_in_tmux() and subprocess.call(
            ["tmux", "select-window", "-t", script.get_window_title()],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ) == 0:
            return True

        selected_script = self.get_selected_item()
        if selected_script is not None:
            selected_script_abs_path = os.path.abspath(selected_script.script_path)

            # TODO: This environment variable is deprecated, remove.
            os.environ["SCRIPT"] = selected_script_abs_path

            self.run_raw(
                lambda script=script: execute_script(
                    script,
                    args=[selected_script_abs_path],
                    cd=len(self.__cmdline_args) == 0,
                    run_script_and_quit=self.__run_script_and_quit,
                )
            )
            if script.cfg["reloadScriptsAfterRun"]:
                logging.info("Reload scripts after running: %s" % script.name)
                self._reload_scripts()
            else:
                if script.cfg["updateSelectedScriptAccessTime"]:
                    selected_script.update_script_access_time()
                self.script_manager.sort_scripts()
                self.refresh()
            return True


def _main():
    global script_server

    log_file = os.path.join(get_data_dir(), "myscripts.log")
    setup_logger(log_to_stderr=False, log_file=log_file, level=logging.DEBUG)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-n",
        "--no-daemon",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--startup",
        action="store_true",
        help="will autorun all scripts with runAtStartup=True",
    )
    parser.add_argument(
        "-t",
        "--tmux",
        action="store_true",
        help="Run in tmux.",
    )
    parser.add_argument(
        "--is-running",
        action="store_true",
        help="Is another instance running?",
    )
    parser.add_argument(
        "-q",
        "--quit",
        action="store_true",
        help="Quit after running any script.",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Specify custom prompt.",
    )
    parser.add_argument(
        "-o",
        "--out-to-file",
        type=str,
        default=None,
        help="Save script output to a file.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="Specify input.",
    )
    parser.add_argument(
        "--args",
        nargs=argparse.REMAINDER,
        help="Command line arguments to pass to scripts.",
    )

    args = parser.parse_args()

    if args.tmux and not is_in_tmux() and has_tmux_session():
        print("Attaching to existing tmux session...")
        subprocess.check_call(["tmux", "attach"])
        return

    # Output if an instance is already running.
    if args.is_running:
        print(f"is_instance_running(): {is_instance_running()}")
        return

    # Check if the daemon should be started.
    start_daemon = True
    if args.no_daemon:
        start_daemon = False
        logging.debug("--no-daemon is specified, set start_daemon = False")
    elif args.input:
        start_daemon = False
        logging.debug("input_text is specified, set start_daemon = False")
    elif args.args:
        start_daemon = False
        logging.debug("args is specified, set start_daemon = False")
    elif args.out_to_file:
        start_daemon = False
        logging.debug("out_to_file is specified, set start_daemon = False")
    elif is_instance_running():
        start_daemon = False
        logging.debug("Instance is already running, set start_daemon = False")
    else:
        logging.debug(f"start_daemon = {start_daemon}")

    logging.info("Python executable: %s" % sys.executable)

    # Add bin folder to PATH
    bin_dir = os.path.join(MYSCRIPT_ROOT, "bin")
    append_to_path_global(bin_dir)

    # Add Python's "Scripts" dir to PATH
    script_dir = os.path.abspath(os.path.join(sys.prefix, "Scripts"))
    append_to_path_global(script_dir)

    setup_env_var(os.environ)

    refresh_env_vars()

    setup_nodejs(install=False)

    # Check if we should run in tmux.
    should_run_in_tmux = args.tmux or (
        not is_in_tmux() and start_daemon and is_termux()
    )
    if should_run_in_tmux:
        tmux_exec = shutil.which("tmux")
        if not tmux_exec:
            raise RuntimeError("tmux is not installed")
        if tmux_exec is not None:
            os.execl(
                tmux_exec,
                "tmux",
                "-f",
                os.path.join(MYSCRIPT_ROOT, "settings", "tmux", ".tmux.conf"),
                "new",
                "-n",
                "myscriptsmgr",
                sys.executable,
                *(x for x in sys.argv if x not in ("-t", "--tmux")),
            )

    hide_terminal_from_taskbar()

    run_at_startup(
        name="myscripts",
        cmdline=quote_arg(os.path.join(MYSCRIPT_ROOT, "myscripts.cmd")) + " --startup",
    )


    script_manager = ScriptManager(start_daemon=start_daemon, startup=args.startup)

    if start_daemon:
        script_server = ScriptServer(script_manager=script_manager)
        script_server.start_server()

    run_script_and_quit = (
        bool(args.input) or args.quit or bool(args.args) or bool(args.out_to_file)
    )

    try:
        _MyScriptMenu(
            cmdline_args=args.args,
            input_text=args.input,
            no_daemon=not start_daemon,
            run_script_and_quit=run_script_and_quit,
            script_manager=script_manager,
            out_to_file=args.out_to_file,
            prompt="run script" if run_script_and_quit else args.prompt,
        ).exec()
    except Exception:
        ExceptionMenu().exec()
        if not run_script_and_quit:
            restart_program()


if __name__ == "__main__":
    _main()
