import os
import subprocess
import tempfile
import time
import uuid

from utils.textutil import truncate_output


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


def _save_full_output(output: str, tool_name: str) -> str:
    output_dir = os.path.join(tempfile.gettempdir(), "coder", "tool-output")
    os.makedirs(output_dir, exist_ok=True)

    full_output_filename = (
        f"tool_{tool_name}_{int(time.time())}_{uuid.uuid4().hex[:8]}.log"
    )
    full_output_path = os.path.join(output_dir, full_output_filename)
    with open(full_output_path, "w", encoding="utf-8") as f:
        f.write(output)
    return full_output_path


def _truncate_output(output: str, tool_name: str) -> str:
    MAX_OUTPUT_LINES = 2000
    MAX_OUTPUT_BYTES = 50 * 1024

    truncated = truncate_output(
        output, max_lines=MAX_OUTPUT_LINES, max_bytes=MAX_OUTPUT_BYTES
    )
    if truncated == output:
        return output

    full_output_path = _save_full_output(output, tool_name)

    return (
        f"{truncated}\n"
        f"Output was truncated, full output saved to: {full_output_path}\n"
        "Use `grep` to search the entire content, or use `read` with offset and limit to view specific sections"
    )


def bash(command: str) -> str:
    """
    Execute a bash command on the system.
    - Use this when you need to perform system operations or run specific commands to accomplish any step in the user's task.
    - Ensure the command is properly formatted and does not contain any harmful instructions.
    """

    output = _run_bash(command)

    return _truncate_output(output, tool_name="bash")
