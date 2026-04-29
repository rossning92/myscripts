import argparse
import logging
import os
import sys

sys.path.insert(
    0, os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + "/../libs")
)

from _script import start_script
from _shutil import prepend_to_path
from utils.logger import setup_logger


def str2bool(value):
    if isinstance(value, bool):
        return value
    if value.lower() in ("yes", "true", "t", "y", "1"):
        return True
    elif value.lower() in ("no", "false", "f", "n", "0"):
        return False
    elif value.lower() == "auto":
        return None
    else:
        raise argparse.ArgumentTypeError("Boolean value expected.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file", nargs="?")
    parser.add_argument("--cd", type=str2bool, default=True)
    parser.add_argument("--restart-instance", type=str2bool, default=True)
    parser.add_argument("--run-in-tmux", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    if args.verbose:
        setup_logger(level=logging.DEBUG)

    # If Python is running in a virtual environment (venv), ensure that the
    # shell executes the Python version located inside the venv.
    prepend_to_path(os.path.dirname(sys.executable))

    start_script(
        file=args.file,
        args=args.args,
        cd=args.cd,
        restart_instance=args.restart_instance,
        run_in_tmux=args.run_in_tmux,
    )
