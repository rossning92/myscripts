#!/usr/bin/env python3
"""Interactively share an existing Syncthing folder with a known device."""

import json
from pathlib import Path
import secrets
import socket
import string
import subprocess
import sys
from typing import Any, NoReturn


def fail(message: str, *, detail: str | None = None) -> NoReturn:
    print(f"Error: {message}", file=sys.stderr)
    if detail:
        print(detail.rstrip(), file=sys.stderr)
    raise SystemExit(1)


def syncthing_cli(*args: str) -> str:
    command = ["syncthing", "cli", *args]
    try:
        result = subprocess.run(
            command,
            check=True,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        fail("the 'syncthing' command was not found in PATH.")
    except subprocess.CalledProcessError as error:
        fail(
            f"Syncthing CLI command failed: {' '.join(command)}",
            detail=error.stderr,
        )
    return result.stdout


def load_json(*args: str) -> dict[str, Any]:
    output = syncthing_cli(*args)
    try:
        value = json.loads(output)
    except json.JSONDecodeError as error:
        fail("Syncthing returned invalid JSON.", detail=str(error))
    if not isinstance(value, dict):
        fail("Syncthing returned an unexpected JSON value.")
    return value


def choose(prompt: str, choices: list[Any]) -> Any:
    while True:
        try:
            answer = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            raise SystemExit(130)
        if answer.lower() in {"q", "quit"}:
            print("Cancelled.")
            raise SystemExit(0)
        if answer.isdigit() and 1 <= int(answer) <= len(choices):
            return choices[int(answer) - 1]
        print(f"Please enter a number from 1 to {len(choices)}, or q to quit.")


def display_name(device: dict[str, Any]) -> str:
    return device.get("name") or "Unnamed device"


def add_folder(folders: list[dict[str, Any]]) -> dict[str, Any]:
    existing_paths = {
        Path(folder["path"]).expanduser().resolve()
        for folder in folders
        if folder.get("path")
    }
    while True:
        try:
            answer = input("Folder path (or q to quit): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            raise SystemExit(130)
        if answer.lower() in {"q", "quit"}:
            print("Cancelled.")
            raise SystemExit(0)
        path = Path(answer).expanduser().resolve()
        if not path.is_dir():
            print("Please enter the path of an existing directory.")
        elif path in existing_paths:
            print("That folder is already configured in Syncthing.")
        else:
            break

    try:
        label = input(f"Folder name [{path.name}]: ").strip() or path.name
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        raise SystemExit(130)

    alphabet = string.ascii_lowercase + string.digits
    folder_id = "-".join(
        "".join(secrets.choice(alphabet) for _ in range(5)) for _ in range(2)
    )
    return {"id": folder_id, "label": label, "path": str(path), "devices": []}


def main() -> None:
    config = load_json("config", "dump-json")
    system = load_json("show", "system")
    local_id = system.get("myID", "")
    devices = config.get("devices", [])
    folders = config.get("folders", [])
    local_device = next(
        (device for device in devices if device.get("deviceID") == local_id), None
    )
    machine_name = (
        display_name(local_device) if local_device else socket.gethostname()
    )

    print(f"Machine: {machine_name}")
    if local_id:
        print(f"Device ID: {local_id}")
    print("\nFolders:")

    devices_by_id = {device.get("deviceID"): device for device in devices}
    for index, folder in enumerate(folders, 1):
        shared_names = [
            display_name(devices_by_id[entry.get("deviceID")])
            for entry in folder.get("devices", [])
            if entry.get("deviceID") in devices_by_id
            and entry.get("deviceID") != local_id
        ]
        sharing = ", ".join(shared_names) if shared_names else "no remote devices"
        label = folder.get("label") or folder.get("id") or "Unnamed folder"
        print(f"  {index}. {label} [{folder.get('id', '?')}]")
        print(f"     {folder.get('path', '(path unavailable)')} (shared with {sharing})")

    print(f"  {len(folders) + 1}. Add a new folder")
    selection = choose(
        "\nSelect a folder to share (or q to quit): ", [*folders, None]
    )
    new_folder = selection is None
    folder = add_folder(folders) if new_folder else selection
    current_device_ids = {
        entry.get("deviceID") for entry in folder.get("devices", [])
    }
    available_devices = [
        device
        for device in devices
        if device.get("deviceID") != local_id
        and device.get("deviceID") not in current_device_ids
    ]

    label = folder.get("label") or folder.get("id") or "Unnamed folder"
    if not available_devices:
        print(f"\n'{label}' is already shared with every known remote device.")
        return

    print(f"\nShare '{label}' with:")
    for index, device in enumerate(available_devices, 1):
        paused = " (paused)" if device.get("paused") else ""
        print(f"  {index}. {display_name(device)}{paused}")
        print(f"     {device.get('deviceID', '(ID unavailable)')}")

    device = choose("\nSelect a machine (or q to quit): ", available_devices)
    folder_id = folder.get("id")
    device_id = device.get("deviceID")
    if not folder_id or not device_id:
        fail("the selected folder or device has no ID.")

    print(f"\nSharing '{label}' with '{display_name(device)}'...")
    if new_folder:
        syncthing_cli(
            "config",
            "folders",
            "add",
            f"--id={folder_id}",
            f"--label={label}",
            f"--path={folder['path']}",
        )
    syncthing_cli(
        "config",
        "folders",
        folder_id,
        "devices",
        "add",
        f"--device-id={device_id}",
    )
    print("Done. Syncthing will offer the folder to that machine.")


if __name__ == "__main__":
    main()
