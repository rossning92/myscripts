import argparse
import os
import subprocess
import sys

sys.path.insert(
    0, os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + "/../libs")
)

from _script import run_script
from _shutil import prepend_to_path
from utils.logger import setup_logger


def _parse_legacy_args():
    """Parse legacy @key=value syntax, return (kwargs, remaining_args)."""
    if len(sys.argv) > 1 and sys.argv[1].startswith("@"):
        kwargs = {}
        for kvp in sys.argv[1][1:].split(":"):
            k, v = kvp.split("=")
            if v == "1":
                kwargs[k] = True
            elif v == "0":
                kwargs[k] = False
            elif v == "auto":
                kwargs[k] = None
        return kwargs, sys.argv[2:]
    return None, sys.argv[1:]


def _parse_args():
    legacy_kwargs, remaining = _parse_legacy_args()
    if legacy_kwargs is not None:
        file = remaining[0] if remaining else None
        rest = remaining[1:] if remaining else []
        return legacy_kwargs, file, rest

    parser = argparse.ArgumentParser(
        description="Run a script with optional flags.",
        usage="run_script [options] <script_path> [script_args ...]",
    )
    parser.add_argument("--new-window", action="store_true", default=False)
    parser.add_argument("--restart-instance", action="store_true", default=False)
    parser.add_argument("--single-instance", action="store_true", default=False)
    parser.add_argument("--cd", action="store_true", default=False)
    parser.add_argument("--command-wrapper", action="store_true", default=False)
    parser.add_argument("--tee", action="store_true", default=False)
    parser.add_argument("--run-script-local", action="store_true", default=False)
    parser.add_argument("--run-in-tmux", action="store_true", default=False)
    parser.add_argument("--log", action="store_true", default=False)

    args, rest = parser.parse_known_args(remaining)

    file = rest[0] if rest else None
    script_args = rest[1:] if rest else []

    kwargs = {
        k: v
        for k, v in {
            "new_window": args.new_window,
            "restart_instance": args.restart_instance,
            "single_instance": args.single_instance,
            "cd": args.cd,
            "command_wrapper": args.command_wrapper,
            "tee": args.tee,
            "run_script_local": args.run_script_local,
            "run_in_tmux": args.run_in_tmux,
        }.items()
        if v
    }

    if args.log:
        setup_logger()

    return kwargs, file, script_args


if __name__ == "__main__":
    kwargs, file, rest_args = _parse_args()

    # If Python is running in a virtual environment (venv), ensure that the
    # shell executes the Python version located inside the venv.
    prepend_to_path(os.path.dirname(sys.executable))

    try:
        run_script(
            file=file,
            args=rest_args,
            **kwargs,
        )
    except subprocess.CalledProcessError as e:
        print(e)
        sys.exit(1)
