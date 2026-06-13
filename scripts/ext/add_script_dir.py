import argparse
import os

from _script import add_script_dir
from utils.menu.filemenu import FileMenu
from utils.menu.inputmenu import InputMenu

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prefix", type=str, nargs="?", default=None)
    parser.add_argument("script_dir", type=str, nargs="?", default=None)

    args = parser.parse_args()
    if args.prefix and args.script_dir:
        script_dir_path = args.script_dir
        prefix = args.prefix
    else:
        script_dir_path = FileMenu(
            prompt="Select script dir", prompt_color="green"
        ).select_directory()
        if not script_dir_path:
            exit(0)

        script_dir_name = os.path.basename(script_dir_path)
        prefix = InputMenu(
            prompt="enter prefix",
            text=os.path.basename(script_dir_path),
            prompt_color="green",
        ).request_input()
        if not prefix:
            exit(0)

    print("Add script directory: %s: %s" % (prefix, script_dir_path))
    add_script_dir(script_dir_path, prefix=prefix)
