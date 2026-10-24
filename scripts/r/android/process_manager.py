import os
import os
import signal
import time
from dataclasses import dataclass

from utils.menu import Menu
from utils.menu.confirmmenu import confirm


@dataclass
class ProcessInfo:
    pid: int
    cpu: float
    name: str
    command_line: str


@dataclass
class ProcessSample:
    name: str
    command_line: str
    cpu_time: int
    start_time: int


class ProcessManagerMenu(Menu[ProcessInfo]):
    def __init__(self):
        self.__clock_ticks = os.sysconf("SC_CLK_TCK")
        self.__previous_sample_time: float | None = None
        self.__previous_samples: dict[int, ProcessSample] = {}
        super().__init__(
            items=[],
            prompt="processes by CPU",
            close_on_selection=False,
            line_number=False,
            timeout_sec=2.0,
        )
        self.add_command(self.__terminate, hotkey="delete", name="terminate", show_in_hotkey_bar=True)
        self.add_command(self.__force_kill, hotkey="alt+x", name="force kill", show_in_hotkey_bar=True)
        self.add_command(self.__refresh, hotkey="ctrl+r", name="refresh")

    def on_created(self):
        self.__refresh()

    def on_timeout(self):
        self.__refresh()

    def on_enter_pressed(self):
        if self.search_by_input():
            return
        self.__terminate()

    def on_escape_pressed(self):
        return True

    def get_item_text(self, item: ProcessInfo) -> str:
        command_line = self.__format_command_line(item.command_line)
        suffix = f" ({command_line})" if command_line else ""
        return f"{item.cpu:>6.1f}%  {item.name}{suffix}"

    def get_item_metadata(self, item: ProcessInfo) -> str:
        return f"Process: {item.name}\nPID: {item.pid}\nCPU: {item.cpu:.1f}%\nCommand: {item.command_line}"

    @staticmethod
    def __format_command_line(command_line: str) -> str:
        aliases = (
            (os.getcwd(), "."),
            (os.path.expanduser("~"), "~"),
            (os.environ.get("PREFIX", ""), "$PREFIX"),
        )
        for path, alias in aliases:
            if path:
                command_line = command_line.replace(path, alias)
        return command_line

    def __refresh(self):
        selected = self.get_selected_item()
        selected_pid = selected.pid if selected else None
        try:
            processes = self.__load_processes()
        except OSError as e:
            self.set_message(f"Failed to load processes: {e}")
            return

        self.items = processes
        self.refresh()
        if selected_pid is not None:
            selected = next(
                (process for process in processes if process.pid == selected_pid), None
            )
            if selected:
                self.set_selected_item(selected)

    def __load_processes(self) -> list[ProcessInfo]:
        sample_time = time.monotonic()
        samples = self.__read_process_samples()
        previous_sample_time = self.__previous_sample_time
        previous_samples = self.__previous_samples
        self.__previous_sample_time = sample_time
        self.__previous_samples = samples

        elapsed = sample_time - previous_sample_time if previous_sample_time else 0
        processes = []
        for pid, sample in samples.items():
            previous = previous_samples.get(pid)
            process_delta = 0
            if previous and previous.start_time == sample.start_time:
                process_delta = max(0, sample.cpu_time - previous.cpu_time)
            cpu = process_delta * 100 / self.__clock_ticks / elapsed if elapsed else 0
            processes.append(ProcessInfo(pid, cpu, sample.name, sample.command_line))

        return sorted(processes, key=lambda item: (-item.cpu, item.pid))

    @staticmethod
    def __read_process_samples() -> dict[int, ProcessSample]:
        samples = {}
        with os.scandir("/proc") as entries:
            for entry in entries:
                if not entry.name.isdigit():
                    continue
                try:
                    with open(f"/proc/{entry.name}/stat", encoding="utf-8") as file:
                        stat = file.read()
                    name_end = stat.rfind(")")
                    name = stat[stat.find("(") + 1 : name_end]
                    fields = stat[name_end + 2 :].split()
                    samples[int(entry.name)] = ProcessSample(
                        name=name,
                        command_line=ProcessManagerMenu.__read_command_line(entry.name),
                        cpu_time=int(fields[11]) + int(fields[12]),
                        start_time=int(fields[19]),
                    )
                except (FileNotFoundError, PermissionError, ValueError):
                    continue
        return samples

    @staticmethod
    def __read_command_line(pid: str) -> str:
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as file:
                return " ".join(
                    arg.decode(errors="replace")
                    for arg in file.read().split(b"\0")
                    if arg
                )
        except (FileNotFoundError, PermissionError):
            return ""

    def __terminate(self):
        self.__kill_selected(signal.SIGTERM, "Terminate")

    def __force_kill(self):
        self.__kill_selected(signal.SIGKILL, "Force kill")

    def __kill_selected(self, sig: signal.Signals, action: str):
        processes = list(self.get_selected_items())
        if not processes:
            return

        description = (
            f"{processes[0].name} (PID {processes[0].pid})"
            if len(processes) == 1
            else f"{len(processes)} processes"
        )
        if not confirm(f"{action} {description}?", prompt_color="red"):
            return

        errors = []
        for process in processes:
            try:
                os.kill(process.pid, sig)
            except OSError as e:
                errors.append(f"{process.pid}: {e}")

        self.set_multi_select(False)
        self.__refresh()
        if errors:
            self.set_message("; ".join(errors))
        else:
            self.set_message(f"Signal sent to {len(processes)} process(es)")


if __name__ == "__main__":
    ProcessManagerMenu().exec()
