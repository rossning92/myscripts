from typing import Optional

from utils.dateutil import format_timestamp, parse_datetime

from .menu import Menu


class InputDateMenu(Menu[str]):
    def __init__(
        self,
        prompt: str = "",
        text="",
        default_ts: Optional[float] = None,
    ):
        items = []
        if default_ts is not None:
            items.append(format_timestamp(default_ts))
        items += [
            "today",
            "yesterday",
            "tmr",
            "tomorrow",
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
            "next monday",
            "next tuesday",
            "next wednesday",
            "next thursday",
            "next friday",
            "next saturday",
            "next sunday",
            "eow",
            "eom",
            "eoy",
        ]
        super().__init__(
            prompt=prompt,
            items=items,
            text=text,
            auto_complete=True,
        )


def input_date(prompt: str, default_ts: Optional[float] = None) -> Optional[float]:
    menu = InputDateMenu(
        prompt=prompt,
        default_ts=default_ts,
    )
    menu.exec()

    val = menu.get_text()
    if val is None:
        return None

    # Return none if input was cancelled
    if val is None:
        return None

    # Return 0 if the user input was empty
    if val == "":
        return 0.0

    # Parse date and time
    try:
        dt = parse_datetime(val)
    except ValueError:
        return None

    # Convert to timestamp
    ts = dt.timestamp()
    return ts
