from utils.menu.shellcmdmenu import ShellCmdMenu

menu = ShellCmdMenu("ping 127.0.0.1")
menu.exec()
print(menu.get_output())
