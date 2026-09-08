import os
import shutil
import subprocess
import sys
from typing import Any, Dict

from ai.utils.tools import Settings


_PERMISSION_ERROR_MARKERS = (
    "permission denied",
    "operation not permitted",
    "read-only file system",
    "access denied",
    "eacces",
    "eperm",
)


class SandboxPermissionError(RuntimeError):
    def __init__(self, output: str):
        super().__init__(output)
        self.output = output


def get_tool_use_preview(args: Dict[str, Any]) -> str:
    command = args.get("command")
    return command if isinstance(command, str) else str(args)


def _build_sandbox_command(command: str) -> list[str]:
    cwd = os.path.realpath(os.getcwd())
    if cwd == os.path.sep:
        raise RuntimeError("Refusing to make the filesystem root sandbox-writable.")

    termux = sys.platform == "android" and bool(os.environ.get("TERMUX_VERSION"))
    executable = "abwrap" if termux else "bwrap"
    sandbox = shutil.which(executable)
    if sandbox is None:
        raise RuntimeError(
            f"Bash sandboxing is enabled, but `{executable}` is not installed."
        )

    shell = shutil.which("bash")
    if shell is None:
        raise RuntimeError("Bash sandboxing is enabled, but `bash` is not installed.")

    args = [sandbox, "--die-with-parent", "--new-session"]
    args.extend(["--android-base"] if termux else ["--unshare-pid"])
    args.extend(["--ro-bind", "/", "/", "--bind", cwd, cwd])
    if not termux:
        args.extend(["--tmpfs", "/tmp", "--proc", "/proc", "--dev", "/dev"])
    return args + ["--chdir", cwd, shell, "-c", command]


def _run_bash(command: str, *, sandbox: bool) -> str:
    args: str | list[str] = _build_sandbox_command(command) if sandbox else command

    result = subprocess.run(
        args,
        shell=not sandbox,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
    )
    output = result.stdout.strip()
    if sandbox and result.returncode != 0 and any(
        marker in output.lower() for marker in _PERMISSION_ERROR_MARKERS
    ):
        raise SandboxPermissionError(output)
    return output


def bash(command: str) -> str:
    """
    Execute a bash command on the system.
    - Use this when you need to perform system operations or run specific commands to accomplish any step in the user's task.
    - Ensure the command is properly formatted and does not contain any harmful instructions.
    """

    return _run_bash(command, sandbox=Settings.sandbox)
