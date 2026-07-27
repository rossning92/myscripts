import numpy as np
from _shutil import read_proc_lines
from utils.clip import set_clip
from utils.menu import Menu

last_result = None
while True:
    lines = ["<refresh>"]
    for ns in ["system", "secure", "global"]:
        lines += [
            "system " + x
            for x in read_proc_lines(["adb", "shell", "settings", "list", ns])
        ]
    lines = [x.replace("=", " ") for x in lines]

    if last_result is not None:
        print(np.setdiff1d(last_result, lines))

    i = Menu(items=lines).exec()
    if lines[i] == "<refresh>":
        last_result = lines
        continue

    set_clip("adb shell settings put " + lines[i])
    break
