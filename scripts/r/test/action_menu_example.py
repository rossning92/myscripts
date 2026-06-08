import datetime

from utils.menu.actionmenu import ActionMenu, action


class MyActionMenu(ActionMenu):
    @action(k="ctrl+k")
    def hello(self):
        input("Hello!\n(press enter to exit...)")

    @action
    def simple_action(self):
        print("Simple action executed")

    @action("Named Action")
    def named_action(self):
        print("Named action executed")

    def on_idle(self):
        now = datetime.datetime.now()
        current_time = now.strftime("%H:%M:%S")
        self.set_message(current_time)


if __name__ == "__main__":
    MyActionMenu().exec()
