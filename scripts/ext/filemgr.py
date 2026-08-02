import argparse
import os

from utils.menu.filemenu import FileMenu

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "dir",
        nargs="?",
        type=str,
        default=None,
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default=None,
    )
    args = parser.parse_args()

    prompt = "filemgr"
    if args.prompt:
        prompt = f"{prompt} > {args.prompt}"

    FileMenu(
        goto=args.dir,
        prompt=prompt,
        config_dir=os.path.join(".config", "filemgr"),
    ).exec()
