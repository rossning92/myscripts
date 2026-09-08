class Settings:
    confirm_command: bool = True
    sandbox: bool = False

    def __init__(self):
        raise TypeError("Settings class should not be instantiated")
