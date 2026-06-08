import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from _filelock import FileLock

from .jsonutil import load_json, save_json
from .platform import is_linux, is_termux, is_windows
from .script.path import get_data_dir, get_my_script_root

_MAX_NOTIFICATIONS = 100


def _get_notifications_path() -> str:
    data_dir = get_data_dir()
    return os.path.join(data_dir, "notifications.json")


def get_notifications() -> List[Dict[str, Any]]:
    path = _get_notifications_path()
    with FileLock("notifications"):
        return load_json(path, default=[])


def clear_notifications(app: str) -> None:
    path = _get_notifications_path()
    with FileLock("notifications"):
        notifications = load_json(path, default=[])
        notifications = [n for n in notifications if n.get("app") != app]
        save_json(path, notifications)


def send_notify(
    text: Optional[str] = None,
    app: str = "myscripts",
    hint: Optional[str] = None,
) -> None:
    # Save notification to history
    path = _get_notifications_path()
    with FileLock("notifications"):
        notifications = load_json(path, default=[])
        notifications.append(
            {
                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "app": app,
                "text": text,
                "hint": hint,
            }
        )

        # Limit history to 100 entries
        if len(notifications) > _MAX_NOTIFICATIONS:
            notifications = notifications[-_MAX_NOTIFICATIONS:]

        save_json(path, notifications)

    if app and text:
        if is_termux():
            subprocess.run(
                ["termux-notification", "-t", app, "-c", text, "--vibrate", "500"],
                check=True,
            )
        elif is_linux():
            try:
                subprocess.run(["notify-send", app, text], check=True)
            except FileNotFoundError:
                pass
        elif is_windows():
            script_path = (
                Path(get_my_script_root()) / "scripts" / "ext" / "send_notification.ps1"
            )
            subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script_path),
                    text,
                    app,
                ],
                check=True,
            )
