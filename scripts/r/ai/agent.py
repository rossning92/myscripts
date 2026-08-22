import argparse
import subprocess

from utils.menu import Menu


AGENTS = {
    "coder": "r/ai/coder.py",
    "codex": "r/codex.sh",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Choose and launch a coding agent")
    parser.add_argument("--context", help="plain-text context")
    args = parser.parse_args()

    menu = Menu(
        prompt="select agent",
        items=list(AGENTS),
        enable_command_palette=False,
        quick_select=True,
    )
    menu.exec()
    agent = menu.get_selected_item()
    if agent is None:
        return 0

    command = ["run_script", AGENTS[agent]]
    if args.context:
        command.extend(["--context", args.context])
    return subprocess.run(command).returncode


if __name__ == "__main__":
    raise SystemExit(main())
