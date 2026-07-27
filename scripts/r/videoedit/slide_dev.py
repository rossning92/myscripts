import glob
import os

from _script import run_script
from utils.menu import Menu

if __name__ == "__main__":
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "slide")
    os.chdir(root)

    files = list(glob.glob(os.path.join("examples", "*", "*.md")))
    idx = Menu(items=files).exec()
    if idx < 0:
        exit(0)
    file = files[idx]

    arr = file.split(os.sep)
    template = arr[1]

    run_script("r/web/open_url_dev.py", ["http://localhost:1244/"])
    run_script(
        "export.js",
        args=["-t", template, "-i", file, "-d", "-p", "1244"],
    )
