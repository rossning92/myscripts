import contextlib
import signal
import subprocess
from dataclasses import dataclass

from utils.menu import Menu


@dataclass(frozen=True)
class BluetoothDevice:
    address: str
    name: str

    def __str__(self) -> str:
        return f"{self.name} ({self.address})"


def get_devices() -> list[BluetoothDevice]:
    output = subprocess.check_output(
        ["bluetoothctl", "devices"], stderr=subprocess.STDOUT, text=True
    )
    devices = []
    for line in output.splitlines():
        parts = line.split(maxsplit=2)
        if len(parts) >= 2 and parts[0] == "Device":
            address = parts[1]
            name = parts[2] if len(parts) == 3 else address
            devices.append(BluetoothDevice(address, name))
    return devices


class BluetoothDeviceMenu(Menu[BluetoothDevice]):
    def __init__(self) -> None:
        super().__init__(prompt="Bluetooth device", timeout_sec=1.0)
        self.refresh()

    def refresh(self) -> None:
        try:
            devices = get_devices()
        except (OSError, subprocess.CalledProcessError) as error:
            self.set_message(_error_message(error))
            return
        if devices == self.items:
            return

        selected = self.get_selected_item()
        search = self.get_input()
        self.clear_items()
        for device in devices:
            self.append_item(device)
        self.set_input(search)

        if selected:
            item_indices = list(self.get_item_indices())
            for row, item_index in enumerate(item_indices):
                if devices[item_index].address == selected.address:
                    self.set_selection(row, row)
                    break

    def on_timeout(self) -> None:
        self.refresh()


def _error_message(error: BaseException) -> str:
    if isinstance(error, subprocess.CalledProcessError):
        return (error.stdout or str(error)).strip()
    return str(error)


def _stop_process(process: subprocess.Popen[object]) -> None:
    if process.poll() is not None:
        return
    process.send_signal(signal.SIGINT)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.terminate()
        process.wait()


def _run_bluetoothctl(
    command: str, address: str, *, agent: str | None = None
) -> None:
    print(f"{command.capitalize()}ing {address}...")
    args = ["bluetoothctl"]
    if agent:
        args.extend(["--agent", agent])
    subprocess.run([*args, command, address], check=True)


def main() -> None:
    print("Scanning for Bluetooth devices...")
    scan_process = subprocess.Popen(
        ["bluetoothctl", "--timeout", "100", "scan", "on"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        menu = BluetoothDeviceMenu()
        menu.exec()
        device = menu.get_selected_item()
    finally:
        _stop_process(scan_process)

    if not device:
        print("Scan cancelled")
        return

    _run_bluetoothctl("pair", device.address, agent="KeyboardDisplay")
    _run_bluetoothctl("trust", device.address)
    _run_bluetoothctl("connect", device.address)


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        main()
