import ctypes
import locale
import os
import subprocess
import sys
from typing import Dict, List, Optional

from _shutil import quote_arg, write_temp_file


def activate_cur_terminal():
    if sys.platform == "win32":
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        ctypes.windll.user32.SetForegroundWindow(hwnd)


def minimize_cur_terminal():
    if sys.platform == "win32":
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        ctypes.windll.user32.ShowWindow(hwnd, 6)


def clear_terminal():
    if sys.platform == "win32":
        subprocess.run(["cls"], check=False, shell=True)
        return

    if os.environ.get("TERM"):
        subprocess.run(["clear"], check=False)
        return

    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def get_terminal_title():
    if sys.platform == "win32":
        MAX_BUFFER = 1024
        title_buff = ctypes.create_unicode_buffer(MAX_BUFFER)
        ret = ctypes.windll.kernel32.GetConsoleTitleW(title_buff, MAX_BUFFER)
        if ret > 0:
            return title_buff.value
    return None


def set_terminal_title(title):
    if sys.platform == "win32":
        ctypes.windll.kernel32.SetConsoleTitleW(title)
    else:
        sys.stdout.write(f"\033]0;{title}\007")
        sys.stdout.flush()


def hide_terminal_from_taskbar():
    # Uses the ITaskbarList COM interface via raw ctypes to remove the window from the taskbar.
    if sys.platform == "win32":
        import ctypes.wintypes

        hwnd = ctypes.windll.kernel32.GetConsoleWindow()

        clsid = (ctypes.c_byte * 16)()
        iid = (ctypes.c_byte * 16)()
        ctypes.windll.ole32.CLSIDFromString(
            "{56FDF344-FD6D-11d0-958A-006097C9A090}", clsid
        )
        ctypes.windll.ole32.CLSIDFromString(
            "{56FDF342-FD6D-11d0-958A-006097C9A090}", iid
        )

        ctypes.windll.ole32.CoInitialize(None)
        p = ctypes.c_void_p()
        ctypes.windll.ole32.CoCreateInstance(
            clsid, None, 1, iid, ctypes.byref(p)
        )

        vtable = ctypes.cast(
            ctypes.cast(p, ctypes.POINTER(ctypes.c_void_p))[0],
            ctypes.POINTER(ctypes.c_void_p * 8),
        ).contents

        # ITaskbarList vtable: 0=QueryInterface, 1=AddRef, 2=Release,
        # 3=HrInit, 4=AddTab, 5=DeleteTab
        HrInit = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p)(vtable[3])
        DeleteTab = ctypes.WINFUNCTYPE(
            ctypes.HRESULT, ctypes.c_void_p, ctypes.wintypes.HWND
        )(vtable[5])

        HrInit(p)
        DeleteTab(p, hwnd)


def enable_windows_vt():
    """Enable Windows virtual terminal processing for console input and output."""
    assert sys.platform == "win32"

    from ctypes import wintypes

    # Windows API constants
    STD_INPUT_HANDLE = -10
    STD_OUTPUT_HANDLE = -11
    ENABLE_VIRTUAL_TERMINAL_INPUT = 0x0200
    ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
    ENABLE_EXTENDED_FLAGS = 0x0080

    kernel32 = ctypes.windll.kernel32

    # Enable VT input
    h_input = kernel32.GetStdHandle(STD_INPUT_HANDLE)
    in_mode = wintypes.DWORD()
    if kernel32.GetConsoleMode(h_input, ctypes.byref(in_mode)):
        new_in_mode = (
            in_mode.value | ENABLE_VIRTUAL_TERMINAL_INPUT | ENABLE_EXTENDED_FLAGS
        )
        kernel32.SetConsoleMode(h_input, new_in_mode)

    # Enable VT output
    h_output = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
    out_mode = wintypes.DWORD()
    if kernel32.GetConsoleMode(h_output, ctypes.byref(out_mode)):
        new_out_mode = out_mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING
        kernel32.SetConsoleMode(h_output, new_out_mode)


def args_to_str(args, shell_type):
    assert type(args) in [list, tuple]
    return " ".join([quote_arg(x, shell_type=shell_type) for x in args])


def wrap_args_tee(args: List[str], out_file: str):
    assert isinstance(args, list)

    if sys.platform == "win32":
        s = (
            "$PSDefaultParameterValues = @{'Out-File:Encoding' = 'utf8'}; & "
            + args_to_str(args, shell_type="powershell")
            + r" | Tee-Object -FilePath %s" % out_file
        )
        tmp_file = write_temp_file(s, ".ps1")
        return ["powershell", tmp_file]
    else:
        return args


def wrap_args_cmd(
    args: List[str],
    title: Optional[str] = None,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> str:
    if sys.platform == "win32":
        cmdline = "cmd /c "
        if title:
            cmdline += "title %s&" % quote_arg(title)
        if cwd:
            cmdline += "cd /d %s&" % quote_arg(cwd)
        if env:
            for k, v in env.items():
                cmdline += "&".join(['set "%s=%s"' % (k, v)]) + "&"
        cmdline += args_to_str(args, shell_type="cmd")
    else:
        cmdline = ""
        if env:
            for k, v in env.items():
                if k != "PATH":
                    cmdline += "%s=%s" % (k, v) + " "
        cmdline += args_to_str(args, shell_type="bash")

    return cmdline
