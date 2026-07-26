import ctypes
import datetime
import glob
import inspect
import json
import locale
import logging
import os
import platform
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path
from time import sleep
from typing import Dict, List, Optional, Union

from utils.jsonutil import load_json, save_json
from utils.printc import printc

logger = logging.getLogger(__name__)


def get_hash(obj, digit=16):
    import hashlib

    if isinstance(obj, str):
        buff = obj.encode("utf-8")
    else:
        buff = repr(obj).encode("utf-8")
    hash_object = hashlib.md5(buff)
    hash = hash_object.hexdigest()[0:digit]
    return hash


@lru_cache(maxsize=None)
def get_ahk_lib_path() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ahk"))


@lru_cache(maxsize=None)
def get_ahk_exe(uia=True) -> str:
    if sys.platform != "win32":
        raise Exception("unsupported platform: %s" % sys.platform)

    is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    if not is_admin and uia:
        ahk_exe = os.path.expandvars(r"%ProgramFiles%\AutoHotkey\AutoHotkeyU64_UIA.exe")
    else:
        ahk_exe = os.path.expandvars(r"%ProgramFiles%\AutoHotkey\AutoHotkeyU64.exe")

    ahk_lib_symlink = os.path.expandvars(r"%USERPROFILE%\Documents\AutoHotkey\Lib")
    if not os.path.exists(ahk_lib_symlink):
        os.makedirs(os.path.dirname(ahk_lib_symlink), exist_ok=True)
        run_elevated(
            r'cmd /c MKLINK /D "{}" "{}"'.format(
                ahk_lib_symlink,
                get_ahk_lib_path(),
            )
        )
    _ahk_initialized = True

    return ahk_exe


def get_home_path():
    return str(Path.home())


def write_temp_file(text: str, file_path: str):
    name, ext = os.path.splitext(file_path)
    if file_path.startswith("."):
        name = ""
        ext = file_path
    else:
        name, ext = os.path.splitext(file_path)

    # Convert into bytes
    if ext in [".bat", ".cmd"]:
        encoding = locale.getpreferredencoding()
    else:
        encoding = "utf-8"
    bytes = text.encode(encoding)
    if ext in [".ahk"]:
        bytes = "\ufeff".encode() + bytes

    if name == "":
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp:
            temp.write(bytes)
            return temp.name
    else:
        full_path = os.path.join(tempfile.gettempdir(), file_path)

        subfolder = os.path.dirname(full_path)
        if subfolder:
            os.makedirs(subfolder, exist_ok=True)

        with open(full_path, "wb") as f:
            f.write(bytes)
            return full_path


def run_ahk(file, wait=False):
    args = [get_ahk_exe(), file]

    with open(os.devnull, "w") as fnull:
        kwargs = {
            "shell": True,  # shell is required for starting UIA process
            "stdin": fnull,
            "stdout": fnull,
            "stderr": fnull,
        }
        if wait:
            subprocess.call(args, **kwargs)
        else:
            return subprocess.Popen(args, **kwargs)


def exec_ahk(script, tmp_script_path=None, wait=True):
    assert sys.platform == "win32"
    if not tmp_script_path:
        tmp_script_path = write_temp_file(script, ".ahk")
    else:
        with open(tmp_script_path, "w", encoding="utf-8") as f:
            f.write("\ufeff")  # BOM utf-8
            f.write(script)
    run_ahk(tmp_script_path, wait=wait)


def chdir(path, expand=True):
    if expand:
        path = os.path.expanduser(path)
    os.chdir(path)


def getch(timeout=-1):
    """Returns None when getch is timeout."""

    if sys.platform == "win32":
        import msvcrt

        time_elapsed = 0.0
        if timeout > 0.0:
            while not msvcrt.kbhit() and time_elapsed < timeout:
                sleep(0.1)
                time_elapsed += 0.1
            if time_elapsed < timeout:
                ch = msvcrt.getch().decode(errors="replace")
            else:
                ch = None
        else:
            ch = msvcrt.getch().decode(errors="replace")

    else:
        import termios
        import tty

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    if ch is not None and ord(ch) == 3:
        raise KeyboardInterrupt
    return ch


def cd(path, expand=True, auto_create_dir=False):
    if expand:
        path = os.path.expanduser(path)
        path = os.path.expandvars(path)

    path = os.path.abspath(path)

    if not os.path.exists(path):
        if auto_create_dir or confirm('"%s" not exist, create?' % path):
            os.makedirs(path)

    os.chdir(path)


def call2(args, check=True, shell=sys.platform == "win32", **kwargs):
    def quote(s):
        if " " in s:
            s = '"%s"' % s
        return s

    if isinstance(args, list):
        s = " ".join([quote(x) for x in args])
    else:
        s = args
    logger.debug("shell_cmd: %s" % s)
    subprocess.run(args, check=check, shell=shell, **kwargs)


def call_echo(args, shell=False, check=True, no_output=False, **kwargs):
    def quote(s):
        if " " in s:
            s = '"%s"' % s
        return s

    if isinstance(args, list):
        s = " ".join([quote(x) for x in args])
    else:
        s = args

    logger.debug("shell_cmd: %s" % s)
    print2("> " + s, color="gray")

    if isinstance(args, str):
        shell = True

    if no_output:
        with fnull() as null:
            ret = subprocess.run(
                args, shell=shell, check=check, stderr=null, stdout=null, **kwargs
            )
    else:
        ret = subprocess.run(args, shell=shell, check=check, **kwargs)
    return ret.returncode


def start_in_new_terminal(args, title=None):
    import shlex

    # Convert argument list to string
    if isinstance(args, list):
        args = [shlex.quote(x) for x in args]

    if sys.platform == "win32":
        args = args.replace("|", "^|")  # Escape '|'
        title_arg = ('"' + title + '"') if title else ""
        args = 'start %s cmd /S /C "%s"' % (title_arg, args)
        subprocess.call(args, shell=True)

    elif sys.platform == "darwin":
        args = args.replace("'", "'\"'\"'")
        args = args.replace('"', '\\"')
        args = """osascript -e 'tell application "Terminal" to do script "%s"'""" % args
        print(args)
        subprocess.call(args, shell=True)


def call(args, cwd=None, env=None, shell=True, highlight=None, check_call=True):
    if highlight is not None:
        return call_highlight(args, shell=shell, cwd=cwd, env=env, highlight=highlight)
    else:
        if check_call:
            return subprocess.check_call(args, shell=shell, cwd=cwd, env=env)
        else:
            return subprocess.call(args, shell=shell, cwd=cwd, env=env)


def run_in_background(cmd):
    # ANSI escape codes for colors
    YELLOW = "\u001b[33;1m"
    RESET = "\033[0m"

    # Enable ANSI escape sequence processing for the console window by calling
    # the SetConsoleMode Windows API with the ENABLE_VIRTUAL_TERMINAL_PROCESSING
    # flag set.
    if sys.platform == "win32":
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)

    def print_output(ps):
        while True:
            line = ps.stdout.readline()
            # stdout is thread-safe
            sys.stdout.buffer.write(YELLOW.encode() + line + RESET.encode())
            sys.stdout.flush()
            if line == "" and ps.poll() is not None:
                break

    ps = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    t = threading.Thread(target=print_output, args=(ps,))
    t.daemon = True  # Kill the thread when program exits
    t.start()
    return ps


def mkdir(path, expand=True):
    if expand:
        path = os.path.expanduser(path)
    os.makedirs(path, exist_ok=True)


def get_pretty_time_delta(seconds):
    sign_string = " ago" if seconds < 0 else ""
    seconds = abs(int(seconds))
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if days > 0:
        return "%d day %02d:%02d:%02d%s" % (days, hours, minutes, seconds, sign_string)
    elif hours > 0:
        return "%dh%s" % (hours, sign_string)
    elif minutes > 0:
        return "%d min%s" % (minutes, sign_string)
    else:
        return "%02d sec%s" % (seconds, sign_string)


def download(url, filename=None, redownload=False, save_to_tmp=False):
    try:
        import requests
    except ImportError:
        subprocess.call([sys.executable, "-m", "pip", "install", "requests"])
        import requests

    if filename is None:
        filename = os.path.basename(url)
        if save_to_tmp:
            filename = os.path.join(tempfile.gettempdir(), filename)

    if os.path.exists(filename) and not redownload:
        print("File already exists: %s" % filename)
        return filename

    print("Download: %s" % url)
    with open(filename, "wb") as f:
        response = requests.get(url, stream=True)
        total = response.headers.get("content-length")

        if total is None:
            f.write(response.content)
        else:
            downloaded = 0
            total = int(total)
            for data in response.iter_content(
                chunk_size=max(int(total / 1000), 1024 * 1024)
            ):
                downloaded += len(data)
                f.write(data)
                done = int(50 * downloaded / total)
                sys.stdout.write("\r[{}{}]".format("|" * done, "." * (50 - done)))
                sys.stdout.flush()
    sys.stdout.write("\n")
    return filename


def copy(src, dst, overwrite=False):
    # Lazy import: distutils import is pretty slow
    from distutils.dir_util import copy_tree

    # Create dirs if not exists
    dir_name = os.path.dirname(dst)
    if dir_name and not os.path.exists(dir_name):
        os.makedirs(dir_name, exist_ok=True)

    if os.path.isdir(src):
        if dst.endswith("/"):
            dst = os.path.abspath(dst + os.path.basename(src))
            copy_tree(src, dst)
            print("%s => %s" % (src, dst))
        else:
            copy_tree(src, dst)
            print("%s => %s" % (src, dst))

    elif os.path.isfile(src):
        if overwrite or not os.path.exists(dst):
            shutil.copy2(src, dst)
            print("%s => %s" % (src, dst))

    else:
        file_list = glob.glob(src)
        if len(file_list) == 0:
            raise Exception("No file being found: %s" % src)

        for f in file_list:
            copy(f, dst)


def run_elevated(args: Union[List[str], str], wait=True, show_terminal_window=True):
    if sys.platform == "win32":
        import win32con
        from win32com.shell import shellcon
        from win32com.shell.shell import ShellExecuteEx

        if isinstance(args, str):
            lpFile, lpParameters = args.split(" ", 1)
        else:
            lpFile = args[0]
            lpParameters = subprocess.list2cmdline(args[1:])

        process_info = ShellExecuteEx(
            nShow=win32con.SW_SHOW if show_terminal_window else win32con.SW_HIDE,
            fMask=shellcon.SEE_MASK_NOCLOSEPROCESS,
            lpVerb="runas",
            lpFile=lpFile,
            lpParameters=lpParameters,
        )
        if wait:
            h = process_info["hProcess"].handle
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            if kernel32.WaitForSingleObject(h, 600000) == 0:  # WAIT_OBJECT_0
                exit_code = ctypes.c_ulong()
                if kernel32.GetExitCodeProcess(h, ctypes.byref(exit_code)):
                    ret = exit_code.value
                else:
                    raise ctypes.WinError(ctypes.get_last_error())
            else:
                raise Exception("WaitForSingleObject failed")

            kernel32.CloseHandle(h)
        else:
            ret = process_info
    else:
        if isinstance(args, str):
            args = "sudo " + args
        else:
            args = ["sudo"] + args
        logging.info("run_elevated(): %s" % args)
        ret = subprocess.call(args, shell=True)
    return ret


def remove(files: Union[str, List[str]]):
    if isinstance(files, str):
        files = [files]

    for file in files:
        if os.path.isdir(file):
            shutil.rmtree(file)
            print("Deleted: %s" % file)
        else:
            for match in glob.glob(file):
                os.remove(match)
                print("Deleted: %s" % match)


def rename(src: str, dst: str, dry_run=False):
    if src == dst:
        print('Skip: "%s" and "%s" are the same file' % (src, dst))
        return

    print("Rename: %s => %s" % (src, dst))
    if not dry_run:
        os.rename(src, dst)


def is_in_wsl() -> bool:
    return "microsoft" in platform.uname().release.lower()


def fnull():
    return open(os.devnull, "w")


def read_lines(file):
    with open(file) as f:
        return f.read().splitlines()


def write_lines(file, lines):
    with open(file, newline="\n") as f:
        f.write("\n".join(lines))


def read_proc_lines(
    args, echo=False, read_err=False, max_lines=None, check=True, **kwargs
):
    ps = subprocess.Popen(
        args,
        stdout=subprocess.PIPE if (not read_err) else None,
        stderr=subprocess.PIPE if read_err else None,
        # bufsize=1,
        **kwargs,
    )

    def terminate():
        nonlocal ps
        if sys.platform == "win32":
            FNULL = open(os.devnull, "w")
            subprocess.call(
                ["taskkill", "/f", "/t", "/pid", "%d" % ps.pid],
                stdout=FNULL,
                stderr=FNULL,
            )
        else:
            ps.send_signal(signal.SIGINT)
            ps.kill()

    line_no = 0
    for line in ps.stderr if read_err else ps.stdout:
        try:
            # process line here
            line = line.strip()
            line = line.decode(errors="ignore")
            if echo:
                print(line)

            yield line
            line_no += 1

            if max_lines and line_no >= max_lines:
                terminate()
                break

        except GeneratorExit:
            terminate()
            raise

    ps.wait()
    if check and ps.returncode != 0:
        raise subprocess.CalledProcessError(ps.returncode, ps.args)


def check_output_echo(args):
    out = ""
    with subprocess.Popen(
        args, stdout=subprocess.PIPE, bufsize=1, universal_newlines=True
    ) as p:
        for line in p.stdout:
            print(line, end="")  # process line here
            out += line

    if p.returncode != 0:
        raise subprocess.CalledProcessError(p.returncode, p.args)

    return out


def get_output(args, **kwargs):
    return (
        subprocess.Popen(
            args, universal_newlines=True, stdout=subprocess.PIPE, **kwargs
        )
        .stdout.read()
        .strip()
    )


def supports_color():
    """
    Returns True if the running system's terminal supports color, and False
    otherwise.
    """
    plat = sys.platform
    supported_platform = plat != "Pocket PC" and (
        plat != "win32" or "ANSICON" in os.environ
    )
    # isatty is not always implemented, #6223.
    is_a_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    return supported_platform and is_a_tty


def print2(msg, color="yellow", end="\n"):
    printc(msg, color=color, end=end)


def call_highlight(args, highlight=None, filter_line=None, **kwargs):
    from colorama import Back, Fore, Style, init

    COLOR_MAP = {
        "black": Fore.LIGHTBLACK_EX,
        "red": Fore.LIGHTRED_EX,
        "green": Fore.LIGHTGREEN_EX,
        "yellow": Fore.LIGHTYELLOW_EX,
        "blue": Fore.LIGHTBLUE_EX,
        "magenta": Fore.LIGHTMAGENTA_EX,
        "cyan": Fore.LIGHTCYAN_EX,
        "white": Fore.LIGHTWHITE_EX,
        "BLACK": Back.BLACK,
        "RED": Back.RED,
        "GREEN": Back.GREEN,
        "YELLOW": Back.YELLOW,
        "BLUE": Back.BLUE,
        "MAGENTA": Back.MAGENTA,
        "CYAN": Back.CYAN,
        "WHITE": Back.WHITE,
    }

    init()

    if highlight is None:
        highlight = {}

    for line in read_proc_lines(args, **kwargs):
        # Filter line by pre-defined functions
        if filter_line:
            line = filter_line(line)
            if line is None:
                continue

        index_color_list = []
        for patt, color in highlight.items():
            # Query ANSI character color codes
            if color in COLOR_MAP:
                color = COLOR_MAP[color]

            for match in re.finditer(patt, line):
                index_color_list.append((match.start(), color))
                index_color_list.append((match.end(), None))
        index_color_list = sorted(index_color_list, key=lambda x: x[0])

        if len(index_color_list) > 0:
            color_stack = [Style.RESET_ALL]
            indices, colors = zip(*index_color_list)
            parts = [line[i:j] for i, j in zip(indices, indices[1:] + (None,))]

            line = line[0 : indices[0]]
            for i in range(len(parts)):
                if colors[i]:
                    line += colors[i]
                    color_stack.append(colors[i])
                else:
                    color_stack.pop()
                    line += color_stack[-1]
                line += parts[i]

        print(line)


def get_short_path_name(long_name):
    assert sys.platform == "win32"

    import ctypes
    from ctypes import wintypes

    _GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
    _GetShortPathNameW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        wintypes.DWORD,
    ]
    _GetShortPathNameW.restype = wintypes.DWORD

    output_buf_size = 0
    while True:
        output_buf = ctypes.create_unicode_buffer(output_buf_size)
        needed = _GetShortPathNameW(long_name, output_buf, output_buf_size)
        if output_buf_size >= needed:
            return output_buf.value
        else:
            output_buf_size = needed


def prepend_to_path(paths: Union[str, List[str]], env: Optional[Dict[str, str]] = None):
    env_dict: Dict[str, str] = env if env is not None else os.environ

    if isinstance(paths, list):
        pass
    elif isinstance(paths, str):
        paths = paths.split(os.pathsep)
    else:
        raise ValueError()
    logging.debug(f"Prepend to PATH: {os.pathsep.join(paths)}")

    if "PATH" in env_dict:
        paths += env_dict["PATH"].split(os.pathsep)
    else:
        paths += os.environ["PATH"].split(os.pathsep)

    # Remove duplicates while keeping the order
    paths = list(dict.fromkeys(paths))

    # Remove directories that no longer exists.
    paths = [p for p in paths if os.path.exists(p)]
    s = os.pathsep.join(paths)

    # Update PATH environmental variable
    env_dict["PATH"] = s


def get_cur_time_str():
    return datetime.datetime.now().strftime("%y%m%d%H%M%S")


def exec_bash(script, wsl=False, echo=False, capture_output=False) -> Optional[str]:
    logging.debug("exec_bash: bash commands: %s" % script)
    args = None
    if sys.platform == "win32":
        if wsl:  # WSL (Windows Subsystem for Linux)
            if not os.path.exists(r"C:\Windows\System32\bash.exe"):
                raise Exception("WSL (Windows Subsystem for Linux) is not installed.")
            args = ["bash.exe", "-c", script]
        else:
            if echo:
                print("> ", end="")
                print2(str(script), color="cyan")
            args = [r"C:\Program Files\Git\bin\bash.exe", "--login", "-i", "-c", script]
    elif os.name == "posix":  # MacOSX
        args = ["bash", "-c", script]
    else:
        raise Exception("Non supported OS version")

    # HACK: disable path conversion
    env = os.environ.copy()
    env["MSYS_NO_PATHCONV"] = "1"
    if capture_output:
        with open(os.devnull) as fnull:
            return subprocess.check_output(
                args,
                env=env,
                text=True,
                stdin=fnull,
                stderr=subprocess.PIPE,
                encoding="utf-8",
            )
    else:
        subprocess.check_call(args, env=env)
        return None


def get_files(cd=False, ignore_dirs=True):
    files = []
    if "FILES" in os.environ:
        files = os.environ["FILES"].split("|")
        files = sorted(files)

    if "CWD" in os.environ and cd:
        cur_folder = os.environ["CWD"]
        os.chdir(cur_folder)
        files = [f.replace(cur_folder, "") for f in files]  # Relative path
        files = [x.lstrip(os.path.sep) for x in files]

    if ignore_dirs:
        files = [x for x in files if os.path.isfile(x)]
    return files


def get_selected_folder():
    files = os.environ["FILES"].split("|")
    folders = [x for x in files if os.path.isdir(x)]
    return folders[0]


def get_current_folder():
    if "CWD" not in os.environ:
        d = input("Enter directory path: ")
        if not d:
            raise Exception("directory cannot be empty.")
        return d
    else:
        return os.environ["CWD"]


def cd_current_dir():
    if "CWD" in os.environ:
        os.chdir(os.environ["CWD"])
    else:
        os.chdir(os.path.expanduser("~"))


def zip_file(path, out_file):
    shutil.make_archive(out_file.rstrip(".zip"), "zip", path)


def unzip(file, to=None):
    print('Unzip "%s"...' % file)
    import zipfile

    if to:
        os.makedirs(to, exist_ok=True)
    else:
        to = "."
    with zipfile.ZipFile(file, "r") as zip:
        zip.extractall(to)


def get_time_str():
    return datetime.datetime.now().strftime("%y%m%d%H%M%S")


def get_date_str():
    return datetime.datetime.now().strftime("%y%m%d")


def make_and_change_dir(path):
    os.makedirs(path, exist_ok=True)
    os.chdir(path)


def get_pretty_mtime(file):
    dt = os.path.getmtime(file)
    now = time.time()
    seconds = int(dt - now)
    return get_pretty_time_delta(seconds)


def get_selected_files() -> List[str]:
    if sys.platform != "win32":
        return []

    try:
        path = os.path.join(os.environ["TEMP"], "ow_explorer_info.json")
        with open(path) as f:
            data = json.load(f)
            return data["selected_files"] if data.get("selected_files") else []
    except Exception as e:
        logging.warning(f"Failed to get explorer info: {e}")
        return []


def get_ip_addresses():
    return [
        info[4][0]
        for info in socket.getaddrinfo(socket.gethostname(), None)
        if info[0] == socket.AddressFamily.AF_INET
    ]


def check_output(args, **kwargs):
    return subprocess.check_output(args, universal_newlines=True, **kwargs)


def convert_to_unix_path(path: str, wsl: bool = False) -> str:
    path = path.replace("\\", "/")
    if re.match(r'^[a-zA-Z]:/(((?![<>:"//|?*]).)+((?<![ .])/)?)*$', path):
        if wsl:
            path = re.sub(
                r"^([a-zA-Z]):", lambda x: "/mnt/" + x.group(0)[0].lower(), path
            )
        else:
            path = re.sub(r"^([a-zA-Z]):", lambda x: "/" + x.group(0)[0].lower(), path)
    return path


def append_to_path_global(path):
    if sys.platform == "win32":
        # Convert to short path in order to remove spaces in path.
        # if " " in path:
        #     path = get_short_path_name(path)

        out = get_output(r"reg query HKCU\Environment /v PATH")
        match = re.search(r"PATH\s+(?:REG_SZ|REG_EXPAND_SZ)\s+(.*)", out)
        if match is None:
            raise Exception(f"Invalid output from reg query: {out}")
        val = match.group(1).strip()
        paths = val.split(";")
        new_paths = []
        for p in paths:
            if os.path.isdir(p):
                new_paths.append(p)
            else:
                logging.debug("Removed from PATH: %s" % p)

        if path not in new_paths:
            new_paths.append(path)
            logging.debug("Added to PATH: %s" % path)

        if new_paths != paths:
            path_str = ";".join(new_paths)
            logging.debug(f"Update PATH using setx: {path_str}")
            with fnull() as nul:
                subprocess.call(["setx", "PATH", path_str], stdout=nul)


def wait_key(prompt=None, timeout=5):
    if prompt is None:
        prompt = "Press enter to skip"
    print2(prompt, color="green", end="")
    ch = getch(timeout=timeout)
    print()
    return ch


def wait_for_key(keys):
    from functools import partial

    import keyboard

    if isinstance(keys, str):
        keys = [keys]

    lock = threading.Event()
    handlers = []

    pressed = None

    def key_pressed(key):
        nonlocal pressed
        pressed = key
        lock.set()

    for key in keys:
        handler = keyboard.add_hotkey(key, partial(key_pressed, key), suppress=True)
        handlers.append(handler)

    lock.wait()

    for handler in handlers:
        keyboard.remove_hotkey(handler)

    return pressed


def wait_until_file_modified(f):
    last_mtime = os.path.getmtime(f)
    while True:
        time.sleep(0.2)
        mtime = os.path.getmtime(f)
        if mtime > last_mtime:
            return


def shell_execute(args):
    from ctypes import c_char_p, c_int, c_ulong, c_void_p
    from ctypes.wintypes import BOOL, DWORD, HANDLE, HINSTANCE, HKEY, HWND

    class ShellExecuteInfo(ctypes.Structure):
        _fields_ = [
            ("cbSize", DWORD),
            ("fMask", c_ulong),
            ("hwnd", HWND),
            ("lpVerb", c_char_p),
            ("lpFile", c_char_p),
            ("lpParameters", c_char_p),
            ("lpDirectory", c_char_p),
            ("nShow", c_int),
            ("hInstApp", HINSTANCE),
            ("lpIDList", c_void_p),
            ("lpClass", c_char_p),
            ("hKeyClass", HKEY),
            ("dwHotKey", DWORD),
            ("hIcon", HANDLE),
            ("hProcess", HANDLE),
        ]

        def __init__(self, **kw):
            ctypes.Structure.__init__(self)
            self.cbSize = ctypes.sizeof(self)
            for field_name, field_value in kw.items():
                setattr(self, field_name, field_value)

    PShellExecuteInfo = ctypes.POINTER(ShellExecuteInfo)

    ShellExecuteEx = ctypes.windll.Shell32.ShellExecuteExA
    ShellExecuteEx.argtypes = (PShellExecuteInfo,)
    ShellExecuteEx.restype = BOOL

    SW_SHOW = 5

    params = args[1:]
    input(params)

    execute_info = ShellExecuteInfo(
        fMask=0,
        hwnd=None,
        lpFile=args[0].encode("utf-8"),
        lpParameters=subprocess.list2cmdline(params).encode("utf-8"),
        lpDirectory=None,
        nShow=SW_SHOW,
    )

    if not all(stream.isatty() for stream in (sys.stdin, sys.stdout, sys.stderr)):
        # TODO: Some streams were redirected, we need to manually work them
        raise NotImplementedError("Redirection is not supported")

    if not ShellExecuteEx(ctypes.byref(execute_info)):
        raise ctypes.WinError()


def setup_nodejs(install=True):
    if sys.platform == "win32":
        NODE_JS_PATH = r"C:\Program Files\nodejs"
        if install and not os.path.exists(NODE_JS_PATH):
            run_elevated("choco install nodejs -y")

        if os.path.exists(NODE_JS_PATH):
            logging.info("Node.js: install path: %s" % NODE_JS_PATH)

            prepend_to_path(
                [
                    NODE_JS_PATH,
                    os.path.expandvars("%APPDATA%\\npm"),
                    os.path.expandvars("%USERPROFILE%\\node_modules\\.bin"),
                    os.path.expandvars("%LOCALAPPDATA%\\Yarn\\bin"),
                    os.path.expandvars("%ProgramFiles%\\Yarn\\bin\\yarn.cmd"),
                    os.path.expandvars("%ProgramFiles(x86)%\\Yarn\\bin\\yarn.cmd"),
                ]
            )

    node_path: List[str] = []
    node_path.append(os.path.abspath(os.path.dirname(__file__) + "/../node_modules"))
    node_path.append(os.path.abspath(os.path.dirname(__file__) + "/../jslib"))

    if sys.platform == "win32":
        # npm global modules
        npm_global_module_path = os.path.expandvars(r"%APPDATA%\npm\node_modules")
        if os.path.exists(npm_global_module_path):
            node_path.append(npm_global_module_path)

        # yarn global modules
        yarn_global_module_path = os.path.expandvars(
            r"%LOCALAPPDATA%\Yarn\Data\global\node_modules"
        )
        if os.path.exists(yarn_global_module_path):
            node_path.append(yarn_global_module_path)

    elif sys.platform in ("linux", "android"):
        # npm global modules
        npm_global_module_path = "/usr/lib/node_modules"
        if os.path.exists(npm_global_module_path):
            node_path.append(npm_global_module_path)

        # yarn global modules
        yarn_global_module_path = os.path.expanduser(
            "~/.config/yarn/global/node_modules"
        )
        if os.path.exists(yarn_global_module_path):
            node_path.append(yarn_global_module_path)

    os.environ["NODE_PATH"] = os.path.pathsep.join(node_path)
    logging.info("Node.js: NODE_PATH: %s" % node_path)


def npm_install(cwd="."):
    cwd = os.path.abspath(cwd)
    if not os.path.exists(os.path.join(cwd, "node_modules")):
        from _pkgmanager import require_package

        require_package("npm")
        call_echo("npm install", cwd=cwd)


def get_next_file_name(file: str, initial_postfix="_2"):
    name, ext = os.path.splitext(file)
    basename = os.path.basename(name)
    folder = os.path.dirname(name)
    match = re.search(r"^(.*?)(\d*)$", basename)

    if match is not None and match.group(2):
        prefix = match.group(1)
        digits = match.group(2)
        len_digits = len(digits)
        digits = int(digits)
        new_digits = ("{:0%dd}" % len_digits).format(digits + 1)
        if len(new_digits) == len_digits:
            new_file = os.path.join(folder, prefix + new_digits + ext)
        else:
            new_file = name + initial_postfix + ext
    else:
        new_file = name + initial_postfix + ext

    if os.path.exists(new_file):
        new_file = name + initial_postfix + ext

    return new_file


def confirm(msg=""):
    msg += " (y/n): "
    print2(msg, end="", color="green")
    ch = getch()
    print()
    return ch == "y"


def write_text_file(content, file, overwrite=True):
    content = content.strip()

    # Don't rewrite the file if content does not change.
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            s = f.read()

        if s == content:
            return False

    if not os.path.exists(file) or overwrite:
        with open(file, "w", encoding="utf-8") as f:
            f.write(content.strip())

    return True


def refresh_env_vars():
    if sys.platform == "win32":
        REG_KEYS = [
            r"HKLM\System\CurrentControlSet\Control\Session Manager\Environment",
            r"HKCU\Environment",
        ]

        def strip_path(p):
            return p.strip().rstrip(os.path.sep)

        paths = [strip_path(x) for x in os.environ["PATH"].split(os.pathsep)]

        for reg_path in REG_KEYS:
            out = subprocess.check_output(
                ["reg", "query", reg_path], universal_newlines=True
            )
            lines = out.splitlines()
            lines = [x.strip() for x in lines if x.strip()]
            lines = lines[1:]  # skip the first line

            for line in lines:
                cols = line.split(maxsplit=2)
                if cols[0].upper() == "PATH":
                    new_paths = cols[2]
                    new_paths = new_paths.split(os.pathsep)

                    for p in new_paths:
                        p = strip_path(p)

                        # Add to PATH if not exists
                        if p and p not in paths:
                            logging.debug("Added to PATH: %s" % p)
                            paths.append(p)

        os.environ["PATH"] = os.pathsep.join(paths)


def get_newest_file(wildcard):
    max_mtime = 0.0
    newest_file = None
    for f in glob.glob(wildcard):
        mtime = os.path.getmtime(f)
        if mtime > max_mtime:
            newest_file = f
            max_mtime = mtime
    return newest_file


def wait_for_new_file(file_pattern, allow_exists=False):
    max_mtime = 0.0
    newest_file = None
    for f in glob.glob(file_pattern):
        mtime = os.path.getmtime(f)
        if mtime > max_mtime:
            newest_file = f
            max_mtime = mtime

    if allow_exists:
        return newest_file
    else:
        print("wait for new file: %s " % file_pattern)
        while True:
            for f in glob.glob(file_pattern, recursive=True):
                mtime = os.path.getmtime(f)
                if mtime > max_mtime:
                    # Wait until file is closed
                    try:
                        os.rename(newest_file, newest_file)
                        print("file created: %s" % newest_file)
                        return newest_file
                    except:
                        time.sleep(0.1)


def update_json(file, dict_):
    dir = os.path.dirname(file)
    if dir:
        os.makedirs(dir, exist_ok=True)
    data = load_json(file, default={})
    data.update(dict_)
    save_json(file, data)


def screen_record(out_file, rect=None, mouse_cursor=True):
    args = [
        "ffmpeg",
        "-y",
        "-f",
        "gdigrab",
        "-draw_mouse",
        "%d" % int(mouse_cursor),
        "-framerate",
        "60",
    ]
    if rect is not None:
        args += [
            "-offset_x",
            "%d" % rect[0],
            "-offset_y",
            "%d" % rect[1],
            "-video_size",
            "%dx%d" % (rect[2], rect[3]),
        ]
    args += [
        "-i",
        "desktop",
        "-c:v",
        "libx264",
        "-crf",
        "0",
        "-preset",
        "ultrafast",
        out_file,
    ]
    ps = subprocess.Popen(args, stdin=subprocess.PIPE)

    def stop():
        ps.stdin.write(b"q")
        ps.stdin.close()

    return stop


def kill_proc(ps):
    if sys.platform == "win32":
        subprocess.call("TASKKILL /F /T /PID %d >NUL 2>NUL" % ps.pid, shell=True)


def send_ctrl_c(ps):
    if ps.poll() is None:
        if sys.platform == "win32":
            try:
                ctypes.windll.kernel32.GenerateConsoleCtrlEvent(0, 0)
                ps.wait()
            except KeyboardInterrupt:
                # It sends ctrl-c to all processes that share the console of the calling
                # process but then ignores it in the python process with an exception
                # handler.
                pass
        else:
            ps.send_signal(signal.SIGINT)
            ps.wait()


def get_temp_file_name(suffix=None):
    with tempfile.TemporaryFile(suffix=suffix) as f:
        return f.name


def find_newest_file(wildcard) -> Optional[str]:
    files = list(glob.glob(wildcard, recursive=True))
    files.sort(key=os.path.getmtime)
    if len(files) > 0:
        return files[-1]
    else:
        return None


def move_file(src, dst, overwrite=False):
    dst = os.path.abspath(dst)
    assert os.path.exists(src)
    os.makedirs(os.path.dirname(dst), exist_ok=True)

    if overwrite and os.path.exists(dst):
        os.remove(dst)

    shutil.move(src, dst)


class MenuItem:
    def __init__(self, name, key, func, caller) -> None:
        self.name = name
        self.caller = caller
        self.key = key
        self.func = func

    def __str__(self) -> str:
        s = ""
        if self.key:
            s += "[%s] " % self.key.replace("\t", "tab").replace("\r", "enter")
        s += self.name
        return s


_menu_items: List[MenuItem] = []


def menu_item(*, key=None, name=None):
    def decorator(func):
        nonlocal name
        if name is None:
            name = func.__name__

        caller = inspect.stack()[1].filename
        _menu_items.append(MenuItem(name=name, key=key, func=func, caller=caller))

        return func

    return decorator


def menu_loop(
    run_periotic=None,
    interval=-1,
    sort_by_name=True,
    unique_key=False,
    all_modules=False,
):
    if all_modules:
        menu_items = _menu_items
    else:
        caller = inspect.stack()[1].filename
        menu_items = list(filter(lambda x: x.caller == caller, _menu_items))

    if sort_by_name:
        menu_items = sorted(menu_items, key=lambda x: x.name)

    if unique_key:
        used_keys = set()
        for item in menu_items:
            if item.key in used_keys:
                raise Exception("Key conflict: %s" % item.key)
            used_keys.add(item.key)

    def print_help():
        print()
        print2("Help Menu")
        print2("---------")

        for menu_item in menu_items:
            print(f"  {menu_item}")

        print("  [h] help")
        print("  [q] quit")
        print()

    def func_wrapper(func):
        start_time = time.time()
        try:
            func()
        except Exception as ex:
            print2("Error: %s" % ex, color="red")
        end_time = time.time()
        if end_time - start_time > 1:
            print2(
                "(finished in %.2f secs)" % (end_time - start_time),
                color="gray",
            )

    print_help()
    while True:
        try:
            if run_periotic is not None and interval > 0:
                while True:
                    ch = getch(timeout=interval)
                    if ch is not None:
                        break
                    else:
                        run_periotic()
            else:
                ch = getch()
        except KeyboardInterrupt:
            sys.exit(0)

        if ch == "h":
            print_help()
        elif ch == "q":
            break
        elif ch == "\t":
            from utils.menu.select import select_option

            index = select_option(menu_items)
            if index >= 0:
                func_wrapper(menu_items[index].func)

        else:
            match = list(filter(lambda x: x.key == ch, menu_items))
            if len(match) == 0:
                print2("Invalid key: %s" % ch, color="yellow")
            else:
                if len(match) == 1:
                    match = match[0]
                else:
                    for i, item in enumerate(match):
                        print("  [%d] %s" % (i + 1, item.name))

                    while True:
                        ch = getch()
                        index = ord(ch) - ord("1")
                        if index >= 0 and index < len(match):
                            match = match[index]
                            break
                        else:
                            print2("(invalid key)")

                func_wrapper(match.func)


def file_is_old(src, dest):
    return not os.path.exists(dest) or os.path.getmtime(src) > os.path.getmtime(dest)


def format_time(sec):
    td = datetime.timedelta(seconds=sec)
    return "%02d:%02d:%02d,%03d" % (
        td.seconds // 3600,
        td.seconds // 60,
        td.seconds % 60,
        td.microseconds // 1000,
    )


def timing(f):
    def wrap(*args, **kwargs):
        time1 = time.time()
        ret = f(*args, **kwargs)
        time2 = time.time()
        print(
            "{:s} function took {:.3f} ms".format(f.__name__, (time2 - time1) * 1000.0)
        )

        return ret

    return wrap


def to_valid_file_name(value):
    string_map = OrderedDict()
    string_map["<="] = "≤"
    string_map[">="] = "≥"
    string_map["<"] = "＜"
    string_map[">"] = "＞"
    string_map[":"] = "："
    string_map["\\"] = "＼"
    string_map["/"] = "／"
    string_map["*"] = "＊"
    string_map["|"] = "｜"
    string_map["?"] = "？"
    string_map['"'] = "”"

    for k, v in string_map.items():
        value = value.replace(k, v)

    return value


def input_with_default(message, default):
    print2("%s (e.g. %s): " % (message, default), color="green", end="")
    s = input()
    return s if s else default


def pause():
    print("(press any key to continue...)")
    getch()


def keep_awake():
    if sys.platform == "win32":
        ES_CONTINUOUS = 0x80000000
        ES_SYSTEM_REQUIRED = 0x00000001
        ES_DISPLAY_REQUIRED = 0x00000002
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
        )


def quote_arg(s, shell_type: str = "cmd") -> str:
    if shell_type == "powershell":
        s = s.replace(" ", "` ").replace("(", "`(").replace(")", "`)")
    elif shell_type == "cmd":
        s = s.replace('"', '""')  # for cmd, we need to escape " with ""
        if " " in s or "\\" in s:  # quote space
            s = '"' + s + '"'
    elif shell_type == "bash":
        s = shlex.quote(s)
    else:
        raise Exception(f"Invalid shell type: {shell_type}")

    return s


def get_env_bool(name):
    if name in os.environ and os.environ[name].strip().isdigit():
        return int(os.environ[name]) > 0
    else:
        return None


def run_at_startup(name, cmdline):
    if sys.platform == "win32":
        args = [
            "reg",
            "add",
            r"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run",
            "/v",
            name,
            "/t",
            "REG_SZ",
            "/d",
            cmdline,
            "/f",
        ]
        subprocess.check_output(args)
        logging.debug("run_at_startup(): %s" % args)


class IgnoreSigInt(object):
    def __enter__(self):
        self.original_handler = signal.getsignal(signal.SIGINT)

        def handler(signum, frame):
            pass

        signal.signal(signal.SIGINT, handler)
        return self

    def __exit__(self, type, value, tb):
        signal.signal(signal.SIGINT, self.original_handler)


def get_hotkey_abbr(hotkey: str):
    return (
        hotkey.lower()
        .replace("win+", "#")
        .replace("ctrl+", "^")
        .replace("alt+", "!")
        .replace("shift+", "+")
    )
