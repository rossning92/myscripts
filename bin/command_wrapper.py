import os
import subprocess
import sys
import time

sys.path.insert(
    0, os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + "/../libs")
)
from utils.notify import clear_notifications, send_notify


def _getch():
    if sys.platform == "win32":
        import msvcrt

        ch = msvcrt.getch().decode(errors="replace")

    else:
        import termios
        import tty

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    if ch is not None and ord(ch) == 3:
        raise KeyboardInterrupt
    return ch


def _format_seconds(seconds: float) -> str:
    minutes = int(seconds // 60)
    remaining_seconds = seconds % 60
    result = f"{minutes:02}:{remaining_seconds:02.0f}"
    return result


if __name__ == "__main__":
    close_on_exit = int(os.environ.get("CMDW_CLOSE_ON_EXIT", "1"))
    window_title = os.environ.get("CMDW_WINDOW_TITLE")

    start_time = time.time()
    args = sys.argv[1:]

    script_path = os.path.abspath(args[0])
    if window_title:
        clear_notifications(app=window_title)

    try:
        code = subprocess.call(args)

        end_time = time.time()
        has_error = code != 0
        if window_title:
            send_notify(app=window_title, hint="error" if has_error else "done")

        duration = end_time - start_time
        keep_terminal_on = not close_on_exit
        if has_error or keep_terminal_on:
            print("---")
            print("(exit code: %d)" % code)
            print(f"(duration: {_format_seconds(duration)} seconds)")
            print("(cmdline: %s)" % args)
            _getch()

    except KeyboardInterrupt:
        print("Ctrl-C")
