import subprocess
from typing import Any, Dict


def get_tool_use_preview(args: Dict[str, Any]) -> str:
    command = args.get("command")
    return command if isinstance(command, str) else str(args)


def _run_bash(command: str) -> str:
    result = subprocess.run(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
    )
    return result.stdout.strip()


def bash(command: str) -> str:
    """
    Execute a bash command on the system.
    - Use this when you need to perform system operations or run specific commands to accomplish any step in the user's task.
    - Ensure the command is properly formatted and does not contain any harmful instructions.
    """

    return _run_bash(command)
