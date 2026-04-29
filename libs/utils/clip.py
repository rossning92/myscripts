import ctypes
import shutil
import subprocess
import sys
import time
from functools import lru_cache


@lru_cache(maxsize=None)
def _is_in_termux():
    return shutil.which("termux-setup-storage") is not None


def _set_clip_win(text: str):
    if sys.platform != "win32":
        raise Exception("The function is only supported on Windows.")

    from ctypes.wintypes import (
        BOOL,
        DWORD,
        HANDLE,
        HGLOBAL,
        HINSTANCE,
        HMENU,
        HWND,
        INT,
        LPCSTR,
        LPVOID,
        UINT,
    )

    u32 = ctypes.windll.user32
    k32 = ctypes.windll.kernel32

    CreateWindowExA = u32.CreateWindowExA
    CreateWindowExA.argtypes = [
        DWORD,
        LPCSTR,
        LPCSTR,
        DWORD,
        INT,
        INT,
        INT,
        INT,
        HWND,
        HMENU,
        HINSTANCE,
        LPVOID,
    ]
    CreateWindowExA.restype = HWND

    DestroyWindow = u32.DestroyWindow
    DestroyWindow.argtypes = [HWND]
    DestroyWindow.restype = BOOL

    OpenClipboard = u32.OpenClipboard
    OpenClipboard.argtypes = [HWND]
    OpenClipboard.restype = BOOL

    CloseClipboard = u32.CloseClipboard
    CloseClipboard.argtypes = []
    CloseClipboard.restype = BOOL

    EmptyClipboard = u32.EmptyClipboard
    EmptyClipboard.argtypes = []
    EmptyClipboard.restype = BOOL

    GlobalAlloc = k32.GlobalAlloc
    GlobalAlloc.argtypes = [UINT, ctypes.c_size_t]
    GlobalAlloc.restype = HGLOBAL

    msvcrt = ctypes.CDLL("msvcrt")
    wcslen = msvcrt.wcslen
    wcslen.argtypes = [ctypes.c_wchar_p]
    wcslen.restype = UINT

    GlobalLock = k32.GlobalLock
    GlobalLock.argtypes = [HGLOBAL]
    GlobalLock.restype = LPVOID

    GlobalUnlock = k32.GlobalUnlock
    GlobalUnlock.argtypes = [HGLOBAL]
    GlobalUnlock.restype = BOOL

    SetClipboardData = u32.SetClipboardData
    SetClipboardData.argtypes = [UINT, HANDLE]
    SetClipboardData.restype = HANDLE

    # This function is heavily based on
    # http://msdn.com/ms649016#_win32_Copying_Information_to_the_Clipboard

    hwnd = CreateWindowExA(0, b"STATIC", None, 0, 0, 0, 0, 0, None, None, None, None)
    try:
        if not hwnd:
            raise Exception("Error calling CreateWindowExA()")

        # http://msdn.com/ms649048
        # If an application calls OpenClipboard with hwnd set to NULL,
        # EmptyClipboard sets the clipboard owner to NULL;
        # this causes SetClipboardData to fail.
        # => We need a valid hwnd to copy something.

        # Open clipboard
        # We may not get the clipboard handle immediately because
        # some other application is accessing it (?)
        # We try for at least 500ms to get the clipboard.
        t = time.time() + 0.5
        success = False
        while time.time() < t:
            success = OpenClipboard(hwnd)
            if success:
                break
            time.sleep(0.01)
        if not success:
            raise Exception("Error calling OpenClipboard")

        try:
            if not EmptyClipboard():
                raise Exception("Error calling EmptyClipboard()")

            if text:
                # http://msdn.com/ms649051
                # If the hMem parameter identifies a memory object,
                # the object must have been allocated using the
                # function with the GMEM_MOVEABLE flag.
                count = wcslen(text) + 1
                GMEM_MOVEABLE = 0x0002
                handle = GlobalAlloc(
                    GMEM_MOVEABLE, count * ctypes.sizeof(ctypes.c_wchar)
                )
                if not handle:
                    raise Exception("Error calling GlobalAlloc()")

                locked_handle = GlobalLock(handle)
                if not locked_handle:
                    raise Exception("Error calling GlobalLock()")

                ctypes.memmove(
                    ctypes.c_wchar_p(locked_handle),
                    ctypes.c_wchar_p(text),
                    count * ctypes.sizeof(ctypes.c_wchar),
                )

                if not GlobalUnlock(handle) and ctypes.get_errno():
                    raise Exception("Error calling GlobalUnlock()")

                CF_UNICODETEXT = 13
                if not SetClipboardData(CF_UNICODETEXT, handle):
                    raise Exception("Error calling SetClipboardData()")

        finally:
            if not CloseClipboard():
                raise Exception("Error calling CloseClipboard()")

    finally:
        if not DestroyWindow(hwnd):
            raise Exception("Error calling DestroyWindow()")


def _get_clip_win() -> str:
    if sys.platform != "win32":
        raise Exception("The function is only supported on Windows.")

    import ctypes.wintypes as w

    CF_UNICODETEXT = 13
    CF_FILENAMEW = 49159  # Format Name = "FileNameW"

    u32 = ctypes.windll.user32
    k32 = ctypes.windll.kernel32

    OpenClipboard = u32.OpenClipboard
    OpenClipboard.argtypes = (w.HWND,)
    OpenClipboard.restype = w.BOOL

    GetClipboardData = u32.GetClipboardData
    GetClipboardData.argtypes = (w.UINT,)
    GetClipboardData.restype = w.HANDLE

    GlobalLock = k32.GlobalLock
    GlobalLock.argtypes = (w.HGLOBAL,)
    GlobalLock.restype = w.LPVOID

    GlobalUnlock = k32.GlobalUnlock
    GlobalUnlock.argtypes = (w.HGLOBAL,)
    GlobalUnlock.restype = w.BOOL

    CloseClipboard = u32.CloseClipboard
    CloseClipboard.argtypes = ()
    CloseClipboard.restype = w.BOOL

    text = ""
    if OpenClipboard(None):
        # Try getting CF_UNICODETEXT first
        h_clip_mem = GetClipboardData(CF_UNICODETEXT)
        if not h_clip_mem:
            # If CF_UNICODETEXT is not available, try FileNameW
            h_clip_mem = GetClipboardData(CF_FILENAMEW)

        if h_clip_mem:
            locked_mem = GlobalLock(h_clip_mem)
            if locked_mem:
                text = ctypes.wstring_at(locked_mem)
                GlobalUnlock(h_clip_mem)
        CloseClipboard()
    return text


def get_clip() -> str:
    if _is_termux():
        return subprocess.check_output(
            ["termux-clipboard-get"],
            universal_newlines=True,
            stderr=subprocess.DEVNULL,
        )

    elif sys.platform == "win32":
        return _get_clip_win()

    elif sys.platform == "darwin":
        return subprocess.check_output(
            ["pbpaste"],
            universal_newlines=True,
        )

    elif sys.platform == "linux":
        try:
            return subprocess.check_output(
                ["xclip", "-out", "-selection", "clipboard"],
                universal_newlines=True,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            return ""


def _get_selection_win():
    if sys.platform != "win32":
        raise Exception("The function is only supported on Windows.")

    LONG = ctypes.c_long
    DWORD = ctypes.c_ulong
    ULONG_PTR = ctypes.POINTER(DWORD)
    WORD = ctypes.c_ushort

    INPUT_KEYBOARD = 1
    VK_CONTROL = 0x11
    KEYEVENTF_KEYUP = 0x0002
    KEY_C = 0x43

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = (
            ("dx", LONG),
            ("dy", LONG),
            ("mouseData", DWORD),
            ("dwFlags", DWORD),
            ("time", DWORD),
            ("dwExtraInfo", ULONG_PTR),
        )

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = (
            ("wVk", WORD),
            ("wScan", WORD),
            ("dwFlags", DWORD),
            ("time", DWORD),
            ("dwExtraInfo", ULONG_PTR),
        )

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = (("uMsg", DWORD), ("wParamL", WORD), ("wParamH", WORD))

    class _INPUTunion(ctypes.Union):
        _fields_ = (("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT))

    class INPUT(ctypes.Structure):
        _fields_ = (("type", DWORD), ("union", _INPUTunion))

    def SendInput(*inputs):
        nInputs = len(inputs)
        LPINPUT = INPUT * nInputs
        pInputs = LPINPUT(*inputs)
        cbSize = ctypes.c_int(ctypes.sizeof(INPUT))
        return ctypes.windll.user32.SendInput(nInputs, pInputs, cbSize)

    def KeybdInput(code, flags=0):
        return INPUT(
            INPUT_KEYBOARD, _INPUTunion(ki=KEYBDINPUT(code, code, flags, 0, None))
        )

    def send_ctrl_c():
        SendInput(KeybdInput(VK_CONTROL), KeybdInput(KEY_C))
        time.sleep(0.1)
        SendInput(
            KeybdInput(VK_CONTROL, KEYEVENTF_KEYUP), KeybdInput(KEY_C, KEYEVENTF_KEYUP)
        )
        time.sleep(0.1)

    send_ctrl_c()

    return _get_clip_win()


@lru_cache(maxsize=None)
def _is_termux():
    return shutil.which("termux-setup-storage") is not None


def get_selection():
    if _is_termux():
        return subprocess.check_output(
            ["termux-clipboard-get"],
            universal_newlines=True,
            stderr=subprocess.DEVNULL,
        )

    elif sys.platform == "linux":
        return subprocess.check_output(
            ["xclip", "-out", "-selection", "primary"],
            universal_newlines=True,
            stderr=subprocess.DEVNULL,
        )

    elif sys.platform == "win32":
        return _get_selection_win()

    else:
        raise Exception(f"Unsupported OS: {sys.platform}")


def set_clip(text: str):
    if _is_in_termux():
        if not shutil.which("termux-clipboard-set"):
            subprocess.check_call(["pkg", "install", "termux-api"])
        subprocess.check_call(["termux-clipboard-set", text])
    elif sys.platform == "linux":
        p = subprocess.Popen(
            ["xclip", "-selection", "c"],
            stdin=subprocess.PIPE,
            close_fds=True,
            # make sure that xclip is not killed so other apps can paste the content
            start_new_session=True,
        )
        p.communicate(input=text.encode("utf-8"))
    elif sys.platform == "darwin":
        p = subprocess.Popen(
            ["pbcopy"],
            stdin=subprocess.PIPE,
            close_fds=True,
        )
        p.communicate(input=text.encode("utf-8"))
    elif sys.platform == "win32":
        _set_clip_win(text)
