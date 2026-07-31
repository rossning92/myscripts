import logging
import subprocess
import threading
from dataclasses import dataclass
from typing import List, Optional

from _script import get_variable, set_variable
from utils.menu import Menu


@dataclass
class DeviceInfo:
    serial: str
    product_name: str
    battery_level: Optional[int]
    wakefulness: Optional[str]
    key: Optional[str]
    is_current: bool
    mode: str = "adb"


_MODE_ORDER = ("adb", "fastboot")


def _assign_keys(devices: List[DeviceInfo]):
    used_keys = set()
    for device in devices:
        device.key = None
    for device in devices:
        for ch in device.product_name.lower():
            if "a" <= ch <= "z" and ch not in used_keys:
                device.key = ch
                used_keys.add(ch)
                break


def _replace_mode(
    devices: List[DeviceInfo],
    lock: threading.Lock,
    mode: str,
    replacement: List[DeviceInfo],
):
    with lock:
        by_mode = {m: [] for m in _MODE_ORDER}
        for d in devices:
            if d.mode != mode:
                by_mode[d.mode].append(d)
        by_mode[mode] = replacement
        merged = [d for m in _MODE_ORDER for d in by_mode[m]]
        _assign_keys(merged)
        devices[:] = merged


def _update_device_list(
    devices: List[DeviceInfo],
    lock: threading.Lock,
    stop_event: threading.Event,
):
    proc: Optional[subprocess.Popen[str]] = None
    try:
        proc = subprocess.Popen(
            ["adb", "track-devices", "-l"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
        )

        while not stop_event.is_set():
            if proc.stdout is None:
                break

            header = proc.stdout.read(4)
            if not header:
                if proc.poll() is not None:
                    break
                continue

            length = int(header, 16)
            payload = proc.stdout.read(length)

            new_devices = []
            current_serial = get_variable("ANDROID_SERIAL")
            for line in payload.splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[1] == "device":
                    info = dict(part.split(":", 1) for part in parts[2:] if ":" in part)
                    new_devices.append(
                        DeviceInfo(
                            serial=parts[0],
                            product_name=info.get("product", "n/a"),
                            battery_level=None,
                            wakefulness=None,
                            key=None,
                            is_current=parts[0] == current_serial,
                            mode="adb",
                        )
                    )

            with lock:
                existing = {d.serial: d for d in devices if d.mode == "adb"}
            for device in new_devices:
                old = existing.get(device.serial)
                if old:
                    device.battery_level = old.battery_level
                    device.wakefulness = old.wakefulness
                else:
                    _refresh_device_status(device)

            _replace_mode(devices, lock, "adb", new_devices)

    except Exception:
        logging.exception("Failed to track adb devices")
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()


def _query_battery_level(serial: str) -> Optional[int]:
    try:
        res = subprocess.run(
            ["adb", "-s", serial, "shell", "dumpsys battery"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                if "level:" in line:
                    return int(line.split(":")[1].strip())
    except Exception:
        pass
    return None


def _query_wakefulness(serial: str) -> Optional[str]:
    try:
        res = subprocess.run(
            ["adb", "-s", serial, "shell", "dumpsys power"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                line = line.strip()
                if line.startswith("mWakefulness="):
                    return line.split("=", 1)[1]
    except Exception:
        pass
    return None


def _refresh_device_status(device: DeviceInfo):
    if device.mode != "adb":
        return
    device.battery_level = _query_battery_level(device.serial)
    device.wakefulness = _query_wakefulness(device.serial)


def _poll_device_status(
    devices: List[DeviceInfo],
    lock: threading.Lock,
    stop_event: threading.Event,
):
    while not stop_event.is_set():
        with lock:
            snapshot = list(devices)
        for device in snapshot:
            if stop_event.is_set():
                break
            _refresh_device_status(device)
        stop_event.wait(10)


def _list_fastboot_devices() -> List[str]:
    try:
        res = subprocess.run(
            ["fastboot", "devices"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return []
    serials = []
    for line in res.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "fastboot":
            serials.append(parts[0])
    return serials


def _query_fastboot_product(serial: str) -> str:
    try:
        res = subprocess.run(
            ["fastboot", "-s", serial, "getvar", "product"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # `getvar` writes "product: <name>" to stderr.
        for line in (res.stderr + res.stdout).splitlines():
            line = line.strip()
            if line.startswith("product:"):
                return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return "fastboot"


def _poll_fastboot_devices(
    devices: List[DeviceInfo],
    lock: threading.Lock,
    stop_event: threading.Event,
):
    while not stop_event.is_set():
        serials = _list_fastboot_devices()

        with lock:
            existing = {d.serial: d for d in devices if d.mode == "fastboot"}

        current_serial = get_variable("ANDROID_SERIAL")
        new_fastboot = []
        for serial in serials:
            old = existing.get(serial)
            if old:
                old.is_current = serial == current_serial
                new_fastboot.append(old)
            else:
                new_fastboot.append(
                    DeviceInfo(
                        serial=serial,
                        product_name=_query_fastboot_product(serial),
                        battery_level=None,
                        wakefulness=None,
                        key=None,
                        is_current=serial == current_serial,
                        mode="fastboot",
                    )
                )

        _replace_mode(devices, lock, "fastboot", new_fastboot)

        stop_event.wait(2)


class DeviceSelectMenu(Menu[DeviceInfo]):
    def __init__(self):
        self.__devices: List[DeviceInfo] = []
        self.__lock = threading.Lock()

        self.__stop_event = threading.Event()

        self.__device_update_thread = threading.Thread(
            target=lambda: _update_device_list(
                self.__devices, self.__lock, self.__stop_event
            ),
            daemon=True,
        )
        self.__device_update_thread.start()

        self.__status_update_thread = threading.Thread(
            target=lambda: _poll_device_status(
                self.__devices, self.__lock, self.__stop_event
            ),
            daemon=True,
        )
        self.__status_update_thread.start()

        self.__fastboot_update_thread = threading.Thread(
            target=lambda: _poll_fastboot_devices(
                self.__devices, self.__lock, self.__stop_event
            ),
            daemon=True,
        )
        self.__fastboot_update_thread.start()

        super().__init__(
            items=self.__devices, prompt="devices", timeout_sec=1.0
        )

        self.add_command(self.__toggle_sleep, hotkey="alt+s")

    def on_exit(self):
        self.__stop_event.set()
        self.__device_update_thread.join()
        self.__status_update_thread.join()
        self.__fastboot_update_thread.join()

    def on_char(self, ch: int | str) -> bool:
        if ch == "0":
            set_variable("ANDROID_SERIAL", "")
            return True
        elif type(ch) is str and len(ch) == 1 and "a" <= ch <= "z":
            for device in self.__devices:
                if ch == device.key:
                    set_variable("ANDROID_SERIAL", device.serial)
                    device.is_current = True
                else:
                    device.is_current = False
            return True
        else:
            return super().on_char(ch)

    def get_item_text(self, item: DeviceInfo) -> str:
        if item.mode == "fastboot":
            return f"[{item.key}] {item.product_name:<12} {item.serial:<15}  fastboot"
        bat = f"{item.battery_level:>3}%" if item.battery_level is not None else "n/a"
        wake = item.wakefulness or "n/a"
        s = f"[{item.key}] {item.product_name:<12} {item.serial:<15}  bat={bat}  {wake}"
        return s

    def get_item_color(self, item: DeviceInfo) -> str:
        if item.is_current:
            return "green"
        else:
            return super().get_item_color(item)

    def __toggle_sleep(self):
        device = self.get_selected_item()
        if device is None:
            return
        if device.mode != "adb":
            self.set_message("Toggle sleep is only available for adb devices")
            return

        label = f"{device.product_name} ({device.serial})"
        self.set_message(f"Toggling sleep on {label}...")

        def do_toggle():
            subprocess.run(
                ["adb", "-s", device.serial, "shell", "input", "keyevent", "KEYCODE_POWER"],
                timeout=5,
            )
            _refresh_device_status(device)
            self.set_message(f"Toggled sleep on {label}: {device.wakefulness or 'n/a'}")

        threading.Thread(target=do_toggle, daemon=True).start()

    def on_timeout(self):
        self.update_screen()


if __name__ == "__main__":
    DeviceSelectMenu().exec()
