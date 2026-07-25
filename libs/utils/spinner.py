SPINNER_CHARS = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


class Spinner:
    _FRAMES = SPINNER_CHARS

    def __init__(self):
        self._index = 0

    @property
    def frame(self) -> str:
        return self._FRAMES[self._index]

    def advance(self) -> None:
        self._index = (self._index + 1) % len(self._FRAMES)
