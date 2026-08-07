import argparse
import os

from _script import start_script
from utils.ziputils import unzip

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("src", type=str)
    parser.add_argument("dest", type=str, nargs="?")
    open_group = parser.add_mutually_exclusive_group()
    open_group.add_argument("--open", dest="open", action="store_true")
    open_group.add_argument("--noopen", dest="open", action="store_false")
    parser.set_defaults(open=True)
    args = parser.parse_args()

    out_dir = unzip([args.src], args.dest)
    if args.open:
        start_script("ext/filemgr.py", args=[os.path.abspath(out_dir)])
