from .actionmenu import action, ActionMenu


class ConfirmMenu(ActionMenu):
    def __init__(self, prompt="", prompt_color="green", **kwargs):
        super().__init__(
            prompt=prompt,
            prompt_color=prompt_color,
            search_mode=False,
            line_number=False,
            **kwargs,
        )
        self.confirmed = False

    @action("yes", k="y")
    def confirm(self):
        self.confirmed = True
        self.close()

    @action("no", k="n")
    def cancel(self):
        self.confirmed = False
        self.close()

    def on_enter_pressed(self):
        if self.get_selected_index() >= 0:
            super().on_enter_pressed()
        else:
            self.confirm()

    def is_confirmed(self):
        return self.confirmed


def confirm(prompt: str, prompt_color: str = "green") -> bool:
    menu = ConfirmMenu(prompt=prompt, prompt_color=prompt_color)
    menu.exec()
    return menu.is_confirmed()
