"""Browse retained ntfy messages in an interactive menu."""

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from utils.menu import Menu
from utils.menu.textmenu import TextMenu


@dataclass(frozen=True)
class NtfyMessage:
    data: dict[str, Any]

    def __str__(self) -> str:
        timestamp = datetime.fromtimestamp(self.data.get("time", 0)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        title = self.data.get("title") or self.data.get("topic") or "ntfy"
        body = " ".join(str(self.data.get("message", "")).splitlines())
        return f"{timestamp}  {title}  {body}"

    def details(self) -> str:
        fields = [
            ("Time", datetime.fromtimestamp(self.data.get("time", 0)).astimezone().isoformat()),
            ("Title", self.data.get("title")),
            ("Message", self.data.get("message")),
            ("Topic", self.data.get("topic")),
            ("Priority", self.data.get("priority")),
            ("Tags", ", ".join(self.data.get("tags", []))),
            ("ID", self.data.get("id")),
        ]
        attachment = self.data.get("attachment")
        if attachment:
            fields.extend(
                [
                    ("Attachment", attachment.get("name")),
                    ("URL", attachment.get("url")),
                ]
            )
        return "\n".join(f"{name}: {value}" for name, value in fields if value)


def fetch_messages(url: str, ntfy: str) -> list[NtfyMessage]:
    result = subprocess.run(
        [ntfy, "subscribe", "--poll", "--since", "all", url],
        check=True,
        capture_output=True,
        text=True,
    )
    messages = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        if data.get("event") == "message":
            messages.append(NtfyMessage(data))
    return sorted(messages, key=lambda item: item.data.get("time", 0), reverse=True)


class NtfyHistoryMenu(Menu[NtfyMessage]):
    def __init__(self, url: str, ntfy: str):
        self.url = url
        self.ntfy = ntfy
        super().__init__(prompt=f"ntfy: {url.rsplit('/', 1)[-1]}", close_on_selection=False)
        self.add_command(self.refresh, hotkey="ctrl+r", pinned=True)
        self.refresh()

    def refresh(self) -> None:
        try:
            messages = fetch_messages(self.url, self.ntfy)
        except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
            if isinstance(error, subprocess.CalledProcessError):
                message = (error.stderr or error.stdout or str(error)).strip()
            else:
                message = str(error)
            self.set_message(message)
            return

        self.clear_items()
        for message in messages:
            self.append_item(message)
        self.set_input("")
        if not messages:
            self.set_message("No retained messages")

    def on_enter_pressed(self) -> None:
        message = self.get_selected_item()
        if message:
            TextMenu(
                text=message.details(),
                prompt=message.data.get("title") or "ntfy message",
            ).exec()


def main() -> None:
    url = os.environ.get("NTFY_URL")
    if not url:
        raise SystemExit("NTFY_URL is not set")
    if not shutil.which("ntfy"):
        raise SystemExit("ntfy is not available in PATH")
    NtfyHistoryMenu(url, "ntfy").exec()


if __name__ == "__main__":
    main()
