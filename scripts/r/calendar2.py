import sys
from datetime import date, timedelta

from utils.getch import getch
from utils.term import clear_terminal, hide_cursor, show_cursor


def change_month(current, amount):
    month_index = current.year * 12 + current.month - 1 + amount
    return date(month_index // 12, month_index % 12 + 1, 1)


def draw(month, interactive=True):
    today = date.today()
    next_month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
    days_in_month = (next_month - month).days

    lines = [f"{month:%B %Y}".center(20), "Mo Tu We Th Fr Sa Su"]
    cells = ["  "] * month.weekday()

    for day in range(1, days_in_month + 1):
        text = f"{day:2}"
        if (month.year, month.month, day) == (
            today.year,
            today.month,
            today.day,
        ):
            if interactive:
                text = f"\033[1;31m{text}\033[0m"
        cells.append(text)

    for index in range(0, len(cells), 7):
        lines.append(" ".join(cells[index:index + 7]))

    if interactive:
        lines.extend(
            [
                "",
                "\033[2m←/→ month  ↑/↓ year  t today  q quit\033[0m",
            ]
        )
        clear_terminal()
        print("\n".join(lines), end="", flush=True)
    else:
        print("\n".join(lines))


def read_key():
    key = getch()

    if sys.platform == "win32" and key in ("\x00", "\ufffd"):
        return {
            "K": "left",
            "M": "right",
            "H": "up",
            "P": "down",
        }.get(getch(), "")

    if key == "\033":
        return {
            "[D": "left",
            "[C": "right",
            "[A": "up",
            "[B": "down",
        }.get((getch() or "") + (getch() or ""), "")

    return key.lower() if key else ""


def main():
    displayed_month = date.today().replace(day=1)

    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        draw(displayed_month, interactive=False)
        return

    hide_cursor()
    try:
        while True:
            draw(displayed_month)
            key = read_key()

            if key == "q":
                break
            if key == "t":
                displayed_month = date.today().replace(day=1)
            elif key == "left":
                displayed_month = change_month(displayed_month, -1)
            elif key == "right":
                displayed_month = change_month(displayed_month, 1)
            elif key == "up":
                displayed_month = change_month(displayed_month, -12)
            elif key == "down":
                displayed_month = change_month(displayed_month, 12)
    finally:
        show_cursor()
        print("\033[0m")


if __name__ == "__main__":
    main()
