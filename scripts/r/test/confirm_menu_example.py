from utils.menu.confirmmenu import ConfirmMenu

if __name__ == "__main__":
    menu = ConfirmMenu(prompt="Do you want to proceed?", prompt_color="green")
    menu.exec()
    print(menu.is_confirmed())
