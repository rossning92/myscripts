import sys
from collections.abc import Sequence
from typing import Any


def wait_for_global_hotkeys(hotkeys: str | Sequence[str]) -> str:
    """Block until one of the global hotkeys is pressed and return its name."""
    hotkey_names = [hotkeys] if isinstance(hotkeys, str) else list(hotkeys)
    if not hotkey_names:
        raise ValueError("At least one hotkey is required")
    if any(not isinstance(hotkey, str) or not hotkey for hotkey in hotkey_names):
        raise ValueError("Hotkeys must be non-empty strings")

    if sys.platform == "linux":
        from Xlib import XK, X, display

        disp = display.Display()
        root = disp.screen().root
        keycodes: dict[int, str] = {}

        try:
            for hotkey in hotkey_names:
                keysym = XK.string_to_keysym(hotkey)
                if keysym == 0:
                    raise ValueError(f"Unknown X11 key name: {hotkey}")

                keycode = disp.keysym_to_keycode(keysym)
                if keycode == 0:
                    raise ValueError(f"No X11 keycode found for: {hotkey}")

                keycodes[keycode] = hotkey
                root.grab_key(
                    keycode, 0, True, X.GrabModeAsync, X.GrabModeAsync
                )
            disp.sync()

            while True:
                event = disp.next_event()
                if event.type == X.KeyPress and event.detail in keycodes:
                    return keycodes[event.detail]
        finally:
            for keycode in keycodes:
                root.ungrab_key(keycode, 0)
            disp.sync()
            disp.close()

    from pynput import keyboard

    resolved_hotkeys: list[tuple[Any, str]] = []
    for hotkey in hotkey_names:
        key_attr = hotkey.lower()
        if hasattr(keyboard.Key, key_attr):
            resolved_hotkey = getattr(keyboard.Key, key_attr)
        else:
            resolved_hotkey = keyboard.KeyCode.from_char(key_attr)
        resolved_hotkeys.append((resolved_hotkey, hotkey))

    pressed_hotkey: str | None = None

    def on_press(key: Any) -> bool | None:
        nonlocal pressed_hotkey
        for resolved_hotkey, hotkey in resolved_hotkeys:
            matches_key = key == resolved_hotkey
            if not matches_key and isinstance(resolved_hotkey, keyboard.KeyCode):
                matches_key = getattr(key, "char", None) == resolved_hotkey.char
            if matches_key:
                pressed_hotkey = hotkey
                return False
        return None

    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()

    if pressed_hotkey is None:
        raise RuntimeError("Global hotkey listener stopped before a hotkey was pressed")
    return pressed_hotkey
