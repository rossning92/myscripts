from utils.menu.dicteditmenu import DictEditMenu

if __name__ == "__main__":
    menu = DictEditMenu(
        {
            "str_value": "Hello!",
            "int_value": 123,
            "bool_value": False,
        }
    )
    menu.exec()
