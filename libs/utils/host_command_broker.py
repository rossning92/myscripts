"""Host commands with approval in the originating tmux window."""

import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time


OUTPUT_LIMIT = 1024 * 1024
MOUNT_PATH = "/run/host-command-broker"
CLIENT_PATH = MOUNT_PATH + "/host-command"
APPROVAL_PROMPT = "Press Enter to approve, or type anything to deny: "

# Copied into a private host directory before the agent starts. The pane gets its
# own terminal; the sandboxed agent cannot approve through its stdin or tools.
APPROVAL = r'''
import json, pathlib, sys
request = json.loads(pathlib.Path(sys.argv[1]).read_text())
for line in request["lines"]:
    print(line)
try:
    approved = input(request["prompt"]) == ""
except (EOFError, KeyboardInterrupt):
    approved = False
receipt = pathlib.Path(sys.argv[2])
pending = receipt.with_suffix(".pending")
pending.write_text("approved" if approved else "denied")
pending.replace(receipt)
sys.exit(0 if approved else 1)
'''

CLIENT = r'''
import argparse, json, os, socket, sys
p = argparse.ArgumentParser(description="Request a host command; requires human approval.")
p.add_argument("--reason", required=True)
p.add_argument("--timeout", type=int, default=300)
p.add_argument("command", nargs=argparse.REMAINDER)
a = p.parse_args()
argv = a.command[1:] if a.command[:1] == ["--"] else a.command
if not argv:
    p.error("supply -- command [args...]")
request = {"argv": argv, "cwd": os.getcwd(), "reason": a.reason, "timeout": a.timeout}
with socket.socket(socket.AF_UNIX) as s:
    s.connect(BROKER_SOCKET)
    s.sendall(json.dumps(request).encode() + b"\n")
    with s.makefile("rb") as f:
        result = json.loads(f.readline(16 * 1024 * 1024))
sys.stdout.write(result.get("stdout", ""))
sys.stderr.write(result.get("stderr", ""))
sys.exit(result["returncode"])
'''


class HostCommandBroker:
    """Mount endpoint read-only at MOUNT_PATH while this context is open.

    Agents invoke CLIENT_PATH with --reason TEXT -- command [args...].
    The host wrapper owns this context and waits for its sandboxed agent here.
    """

    def __enter__(self):
        self.origin_pane = os.environ.get("TMUX_PANE")
        self.tmux_executable = shutil.which("tmux")
        if not os.environ.get("TMUX") or not self.origin_pane or not self.tmux_executable:
            raise RuntimeError("Run the agent wrapper inside tmux for host approvals")
        self.temp = tempfile.TemporaryDirectory(prefix="host-command-broker-", dir="/tmp")
        self.root = Path(self.temp.name)
        self.endpoint = self.root / "endpoint"
        self.endpoint.mkdir(mode=0o700)
        self.approval = self.root / "approve.py"
        self.approval.write_text(APPROVAL)
        client = self.endpoint / Path(CLIENT_PATH).name
        client.write_text(
            f"#!{sys.executable} -I\n"
            + "BROKER_SOCKET = " + repr(MOUNT_PATH + "/socket") + "\n"
            + CLIENT
        )
        client.chmod(0o500)
        self.socket = socket.socket(socket.AF_UNIX)
        self.socket.bind(str(self.endpoint / "socket"))
        self.socket.listen(1)
        self.socket.settimeout(0.5)
        self.closed = threading.Event()
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()
        return self

    def serve(self):
        while not self.closed.is_set():
            try:
                connection, _ = self.socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with connection:
                try:
                    connection.settimeout(1)
                    with connection.makefile("rb") as reader:
                        raw = reader.readline(65537)
                    if len(raw) > 65536 or not raw.endswith(b"\n"):
                        raise ValueError("Request too large or incomplete")
                    result = self.handle(json.loads(raw))
                except Exception as error:
                    result = {"returncode": 1, "stderr": f"Host request failed: {error}\n"}
                try:
                    connection.sendall(json.dumps(result).encode() + b"\n")
                except OSError:
                    pass

    def handle(self, request):
        if not isinstance(request, dict):
            raise ValueError("Request must be a JSON object")
        argv = request.get("argv")
        cwd = request.get("cwd")
        reason = request.get("reason")
        timeout = request.get("timeout", 300)
        if (not isinstance(argv, list) or not argv or not argv[0]
                or not all(isinstance(arg, str) and "\0" not in arg for arg in argv)
                or not isinstance(cwd, str) or "\0" in cwd or not Path(cwd).is_absolute()
                or not isinstance(reason, str) or not reason.strip()
                or type(timeout) is not int or not 1 <= timeout <= 3600):
            raise ValueError("Invalid command, directory, reason, or timeout (1-3600 seconds)")
        approval_request = {
            "lines": ["Reason: " + ascii(reason), "Directory: " + ascii(cwd),
                      "Command: " + ascii(shlex.join(argv)), ""],
            "prompt": APPROVAL_PROMPT,
        }
        request_path = self.root / "request.json"
        request_path.write_text(json.dumps(approval_request))
        receipt = self.root / "approved"
        receipt.unlink(missing_ok=True)
        approval_command = shlex.join([
            sys.executable, "-I", str(self.approval), str(request_path), str(receipt),
        ])
        approved = self.ask_approval(
            approval_command, receipt,
            [*approval_request["lines"], approval_request["prompt"]],
        )
        if not approved or self.closed.is_set():
            return {"returncode": 1, "stderr": "Host command denied.\n"}
        # No shell expansion, inherited stdin, or sandbox-supplied environment.
        # Output uses files so a noisy command cannot exhaust broker memory.
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            process = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL,
                                       stdout=stdout, stderr=stderr, start_new_session=True)
            code, timed_out = self.wait(process, timeout)
            stdout.seek(0)
            stderr.seek(0)
            out = stdout.read(OUTPUT_LIMIT + 1)
            err = stderr.read(OUTPUT_LIMIT + 1)
        stderr_text = err[:OUTPUT_LIMIT].decode(errors="replace")
        if max(len(out), len(err)) > OUTPUT_LIMIT:
            stderr_text += "\nOutput truncated.\n"
        if timed_out:
            stderr_text += "\nHost command timed out.\n"
        return {
            "returncode": code if code >= 0 else 128 - code,
            "stdout": out[:OUTPUT_LIMIT].decode(errors="replace"),
            "stderr": stderr_text,
        }

    def tmux(self, *args):
        return subprocess.run(
            [self.tmux_executable, *args], stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=5,
        )

    def ask_approval(self, command, receipt, lines):
        dimensions = self.tmux(
            "display-message", "-p", "-t", self.origin_pane,
            "#{pane_width} #{pane_height}",
        )
        if dimensions.returncode:
            return False
        width, available = map(int, dimensions.stdout.split())
        if width < 1 or available < 3:
            return False
        height = sum(max(1, (len(line) + width - 1) // width) for line in lines)
        # Leave room for the divider and the original pane.
        height = min(height, available - 2)
        # Select the new pane within the originating window, without changing windows.
        result = self.tmux(
            "split-window", "-v", "-l", str(height), "-t",
            self.origin_pane, "-P", "-F", "#{pane_id}", command,
        )
        pane = result.stdout.strip()
        if result.returncode or not pane.startswith("%") or not pane[1:].isdigit():
            return False
        deadline = time.monotonic() + 3600
        try:
            while not self.closed.is_set() and time.monotonic() < deadline:
                if receipt.exists():
                    return receipt.read_text() == "approved"
                panes = self.tmux("list-panes", "-a", "-F", "#{pane_id}")
                if panes.returncode or pane not in panes.stdout.splitlines():
                    # The UI can write its receipt just before the pane exits.
                    return receipt.exists() and receipt.read_text() == "approved"
                self.closed.wait(0.5)
            return False
        finally:
            self.tmux("kill-pane", "-t", pane)

    def wait(self, process, timeout):
        deadline = time.monotonic() + timeout
        while process.poll() is None:
            if self.closed.wait(0.2) or time.monotonic() >= deadline:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                return 124, not self.closed.is_set()
        return process.returncode, False

    def __exit__(self, *exc):
        self.closed.set()
        self.socket.close()
        self.thread.join()
        self.temp.cleanup()
