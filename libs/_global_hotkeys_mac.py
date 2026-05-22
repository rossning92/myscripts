#!/usr/bin/env python3
"""Global hotkey listener for macOS using CGEventTap (no third-party tools needed).

Requires: pip install pyobjc-framework-Quartz
Requires: Accessibility permission in System Settings > Privacy & Security > Accessibility
"""

import json
import os
import signal
import subprocess
import sys

import Quartz
from Quartz import (
    CFMachPortCreateRunLoopSource,
    CFRunLoopAddSource,
    CFRunLoopGetCurrent,
    CFRunLoopRun,
    CGEventGetFlags,
    CGEventGetIntegerValueField,
    CGEventMaskBit,
    CGEventTapCreate,
    kCFRunLoopCommonModes,
    kCGEventFlagMaskAlternate,
    kCGEventFlagMaskCommand,
    kCGEventFlagMaskControl,
    kCGEventFlagMaskShift,
    kCGEventKeyDown,
    kCGHeadInsertEventTap,
    kCGSessionEventTap,
)

KEYCODE_MAP = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7,
    "c": 8, "v": 9, "b": 11, "q": 12, "w": 13, "e": 14, "r": 15,
    "y": 16, "t": 17, "1": 18, "2": 19, "3": 20, "4": 21, "6": 22,
    "5": 23, "9": 25, "7": 26, "8": 28, "0": 29,
    "o": 31, "u": 32, "i": 34, "p": 35,
    "l": 37, "j": 38, "k": 40, "n": 45, "m": 46,
    "return": 36, "enter": 36, "tab": 48, "space": 49,
    "backspace": 51, "del": 51, "escape": 53, "esc": 53,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97,
    "f7": 98, "f8": 100, "f9": 101, "f10": 109, "f11": 103, "f12": 111,
    "[": 33, "]": 30, ",": 43, ".": 47, "=": 24,
    "-": 27, ";": 41, "'": 39, "/": 44, "\\": 42, "`": 50,
    "left": 123, "right": 124, "down": 125, "up": 126,
    "delete": 117, "home": 115, "end": 119, "pageup": 116, "pagedown": 121,
}

MODIFIER_MAP = {
    "cmd": kCGEventFlagMaskCommand,
    "command": kCGEventFlagMaskCommand,
    "win": kCGEventFlagMaskCommand,
    "ctrl": kCGEventFlagMaskControl,
    "control": kCGEventFlagMaskControl,
    "shift": kCGEventFlagMaskShift,
    "alt": kCGEventFlagMaskAlternate,
    "option": kCGEventFlagMaskAlternate,
    "opt": kCGEventFlagMaskAlternate,
}

MODIFIER_MASK = (
    kCGEventFlagMaskCommand
    | kCGEventFlagMaskControl
    | kCGEventFlagMaskShift
    | kCGEventFlagMaskAlternate
)

PID_FILE = "/tmp/myscripts_hotkeys.pid"


def parse_hotkey(hotkey_str):
    parts = hotkey_str.lower().split("+")
    key = parts[-1]
    modifiers = parts[:-1]

    keycode = KEYCODE_MAP.get(key)
    if keycode is None:
        raise ValueError(f"Unknown key: {key}")

    flags = 0
    for mod in modifiers:
        flag = MODIFIER_MAP.get(mod)
        if flag is None:
            raise ValueError(f"Unknown modifier: {mod}")
        flags |= flag

    return flags, keycode


def main():
    config_path = sys.argv[1]
    with open(config_path) as f:
        config = json.load(f)

    hotkeys = []
    for entry in config:
        try:
            flags, keycode = parse_hotkey(entry["hotkey"])
            hotkeys.append((flags, keycode, entry["command"]))
        except ValueError as e:
            print(f"Skipping hotkey {entry['hotkey']}: {e}", file=sys.stderr)

    def callback(proxy, event_type, event, refcon):
        keycode = CGEventGetIntegerValueField(
            event, Quartz.kCGKeyboardEventKeycode
        )
        flags = CGEventGetFlags(event) & MODIFIER_MASK
        for hk_flags, hk_keycode, command in hotkeys:
            if keycode == hk_keycode and flags == hk_flags:
                subprocess.Popen(command, shell=True)
                return None
        return event

    tap = CGEventTapCreate(
        kCGSessionEventTap,
        kCGHeadInsertEventTap,
        0,
        CGEventMaskBit(kCGEventKeyDown),
        callback,
        None,
    )

    if tap is None:
        print(
            "ERROR: Could not create event tap. "
            "Grant Accessibility permission in "
            "System Settings > Privacy & Security > Accessibility.",
            file=sys.stderr,
        )
        sys.exit(1)

    source = CFMachPortCreateRunLoopSource(None, tap, 0)
    CFRunLoopAddSource(CFRunLoopGetCurrent(), source, kCFRunLoopCommonModes)
    Quartz.CGEventTapEnable(tap, True)

    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    print(f"Listening for {len(hotkeys)} hotkeys (PID {os.getpid()})...")
    CFRunLoopRun()


if __name__ == "__main__":
    main()
