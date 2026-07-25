from time import sleep

from utils.menu.asynctaskmenu import AsyncTaskMenu

AsyncTaskMenu(lambda: sleep(3)).exec()
