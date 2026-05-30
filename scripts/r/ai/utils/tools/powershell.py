import os
import subprocess
import sys
import tempfile


def _run_powershell(command: str) -> str:
    ps_exe = "powershell" if sys.platform == "win32" else "pwsh"

    with tempfile.NamedTemporaryFile(
        suffix=".ps1", delete=False, mode="w", encoding="utf-8-sig"
    ) as f:
        script_file = f.name
        f.write(command)

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        log_file = f.name

    try:
        with open(log_file, "w", encoding="utf-8") as log_fh:
            subprocess.run(
                [ps_exe, "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", script_file],
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                check=False,
            )

        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            return f.read().strip()

    finally:
        if os.path.exists(script_file):
            os.remove(script_file)
        if os.path.exists(log_file):
            os.remove(log_file)


def powershell(command: str) -> str:
    """
    Execute a PowerShell command on the system.
    - Use this when you need to perform system operations or run specific commands to accomplish any step in the user's task.
    - Ensure the command is properly formatted and does not contain any harmful instructions.
    """

    return _run_powershell(command)
