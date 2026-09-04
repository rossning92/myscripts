import getpass
import subprocess
import unicodedata
from dataclasses import dataclass

from utils.menu import Menu
from utils.menu.confirmmenu import confirm


def _pad_display(text: str, width: int) -> str:
    display_width = 0
    for char in text:
        if not unicodedata.combining(char):
            display_width += 2 if unicodedata.east_asian_width(char) in "WF" else 1
    return text + " " * max(0, width - display_width)


def _split_terse_line(line: str) -> list[str]:
    """Split one escaped, colon-separated line produced by ``nmcli -t``."""
    fields: list[str] = []
    field: list[str] = []
    escaped = False
    for char in line:
        if escaped:
            field.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ":":
            fields.append("".join(field))
            field = []
        else:
            field.append(char)
    if escaped:
        field.append("\\")
    fields.append("".join(field))
    return fields


@dataclass(frozen=True)
class WifiNetwork:
    active: bool
    ssid: str
    security: str
    bssid: str = ""
    signal: int = 0
    frequency: int = 0
    connection_uuid: str | None = None

    def __str__(self) -> str:
        security = self.security if self.security and self.security != "--" else "open"
        if self.frequency < 3000:
            band = "2.4G"
        elif self.frequency < 5900:
            band = "5G"
        else:
            band = "6G"
        ssid = f"{self.ssid} (saved)" if self.connection_uuid else self.ssid
        text = (
            f"{_pad_display(ssid, 32)} "
            f"{band:>4} {self.signal:>3}% {security}"
        )
        return f"\033[32m{text}\033[0m" if self.active else text


def _nmcli_output(args: list[str]) -> str:
    return subprocess.check_output(
        ["nmcli", *args], stderr=subprocess.STDOUT, text=True
    )


def get_networks(
    saved_connections: dict[str, tuple[str, ...]] | None = None,
) -> list[WifiNetwork]:
    saved_connections = saved_connections or {}
    output = _nmcli_output(
        [
            "-t",
            "--escape",
            "yes",
            "-f",
            "IN-USE,SSID,BSSID,FREQ,SIGNAL,SECURITY",
            "device",
            "wifi",
            "list",
        ]
    )
    networks: dict[str, WifiNetwork] = {}
    for line in output.splitlines():
        fields = _split_terse_line(line)
        if len(fields) != 6 or not fields[1]:
            continue
        active, ssid, bssid, frequency, signal, security = fields
        connection_uuids = saved_connections.get(ssid, ()) or (None,)
        for connection_uuid in connection_uuids:
            network = WifiNetwork(
                active == "*",
                ssid,
                security,
                bssid,
                int(signal),
                int(frequency.split()[0]),
                connection_uuid,
            )
            key = connection_uuid or bssid
            current = networks.get(key)
            if (
                current is None
                or network.active
                or (not current.active and network.signal > current.signal)
            ):
                networks[key] = network
    return list(networks.values())


def get_saved_connections() -> dict[str, tuple[str, ...]]:
    output = _nmcli_output(
        ["-t", "--escape", "yes", "-f", "UUID,TYPE", "connection", "show"]
    )
    connections: dict[str, list[str]] = {}
    for line in output.splitlines():
        fields = _split_terse_line(line)
        if len(fields) == 2 and fields[1] in ("802-11-wireless", "wifi"):
            uuid = fields[0]
            ssid = _nmcli_output(
                [
                    "--escape",
                    "no",
                    "-g",
                    "802-11-wireless.ssid",
                    "connection",
                    "show",
                    "uuid",
                    uuid,
                ]
            ).strip()
            if ssid:
                connections.setdefault(ssid, []).append(uuid)
    return {ssid: tuple(uuids) for ssid, uuids in connections.items()}


class WifiMenu(Menu[WifiNetwork]):
    def __init__(self):
        super().__init__(prompt="Wi-Fi", close_on_selection=False)
        self.add_command(self.scan, hotkey="ctrl+r", pinned=True)
        self.add_command(self.enable_wifi, hotkey="alt+e", pinned=True)
        self.add_command(self.disable_wifi, hotkey="alt+d", pinned=True)
        self.add_command(self._delete_network, hotkey="ctrl+d", pinned=True)
        self.refresh()

    def refresh(self) -> None:
        try:
            networks = get_networks(get_saved_connections())
        except (OSError, subprocess.CalledProcessError) as error:
            networks = []
            self.set_message(_error_message(error))
        self.clear_items()
        for item in networks:
            self.append_item(item)
        self.set_input("")

    def scan(self) -> None:
        if self._run_nmcli(["device", "wifi", "rescan"]):
            self.refresh()

    def enable_wifi(self) -> None:
        if self._run_nmcli(["radio", "wifi", "on"]):
            self.refresh()

    def disable_wifi(self) -> None:
        if self._run_nmcli(["radio", "wifi", "off"]):
            self.refresh()

    def _delete_network(self) -> None:
        network = self.get_selected_item()
        if not network or not network.connection_uuid:
            self.set_message("Selected network is not saved")
            return
        if not confirm(f"Forget {network.ssid}?"):
            return
        if self._run_nmcli(
            ["connection", "delete", "uuid", network.connection_uuid]
        ):
            self.refresh()

    def _run_nmcli(self, args: list[str]) -> bool:
        try:
            subprocess.run(
                ["nmcli", *args], capture_output=True, text=True, check=True
            )
            return True
        except (OSError, subprocess.CalledProcessError) as error:
            self.set_message(_error_message(error))
            return False

    def _connect(self, network: WifiNetwork) -> None:
        if network.connection_uuid:
            args = [
                "connection",
                "up",
                "uuid",
                network.connection_uuid,
                "ap",
                network.bssid,
            ]
        else:
            args = [
                "device",
                "wifi",
                "connect",
                network.ssid,
                "bssid",
                network.bssid,
            ]
            if network.security and network.security != "--":
                password = self.run_raw(lambda: getpass.getpass("Password: "))
                if not password:
                    self.set_message("Connection cancelled: empty password")
                    return
                args.extend(["password", password])
        if self._run_nmcli(args):
            self.refresh()

    def on_enter_pressed(self):
        item = self.get_selected_item()
        if item:
            self._connect(item)


def _error_message(error: BaseException) -> str:
    if isinstance(error, subprocess.CalledProcessError):
        return (error.stderr or error.stdout or str(error)).strip()
    return str(error)


if __name__ == "__main__":
    WifiMenu().exec()
