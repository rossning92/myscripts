from utils.menu import Menu


class MyMenu(Menu):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.add_command(lambda: self.set_message("alt+z pressed"), hotkey="alt+z")
        self.add_command(
            lambda: self.set_message("alt+enter pressed"), hotkey="alt+enter"
        )
        self.add_command(
            lambda: self.set_message("ctrl+space triggered"), hotkey="ctrl+space"
        )

    def on_focus_gained(self):
        self.set_message("Focus gained")

    def on_focus_lost(self):
        self.set_message("Focus lost")


def main():
    menu = MyMenu(
        items=[
            "Apple",
            "Banana",
            "Cherry",
            "Date",
            "Elderberry",
            "Fig",
            "Grape",
            "Honeydew",
            "Kiwi",
            "Lemon",
        ],
        prompt="fruit",
        debug=True,
        wrap_text=True,
        auto_complete=True,
    )
    menu.exec()


if __name__ == "__main__":
    main()
