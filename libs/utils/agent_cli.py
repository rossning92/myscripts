"""Shared setup and process isolation for interactive agent CLIs."""

import fnmatch
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from contextlib import nullcontext

from utils.host_command_broker import CLIENT_PATH, MOUNT_PATH, HostCommandBroker
from utils.term import set_terminal_title
from utils.term.title import SOCKET_ENV, TerminalTitleRelay

WRITABLE_ROOTS = (
    Path.home() / ".android",
    Path.home() / ".gradle",
    Path.home() / ".cache" / "uv",
    # Godot
    Path.home() / ".config" / "godot",
    Path.home() / ".cache" / "godot",
    Path.home() / ".local" / "share" / "godot",
)


HOST_ACCESS_INSTRUCTIONS = (
    "You run inside Bubblewrap. For a command that needs host access, use "
    f'{CLIENT_PATH} --reason "why host access is needed" '
    '-- command arg... . The host opens an approval pane in the originating tmux window. '
    "Never approve your own request or interact with the approval pane. "
    "Each request needs approval; denial means do not retry without new user direction. "
    "Use --timeout SECONDS before -- for commands longer than 300 seconds (max 3600). "
    "Shell syntax requires an explicit bash -c argument. Host commands have no interactive stdin."
)


def external_sandbox_enabled():
    try:
        process_root = os.readlink("/proc/self/root")
    except OSError:
        process_root = ""
    return sys.platform == "linux" and not fnmatch.fnmatch(
        process_root, "*/com.termux/files/usr/var/lib/proot-distro/containers/*/rootfs"
    )


def take_context(args):
    if args[:1] != ["--context"]:
        return "", args
    if len(args) < 2:
        raise ValueError("--context requires a value")
    return args[1], args[2:]


def prepare_cli(name, package, *, project_dir_env):
    os.chdir(Path(__file__).resolve().parents[2])
    if os.environ.get(project_dir_env):
        os.chdir(os.environ[project_dir_env])
    npm_prefix = Path.home() / ".npm-global"
    npm_bin = npm_prefix if sys.platform == "win32" else npm_prefix / "bin"
    os.environ["PATH"] = str(npm_bin) + os.pathsep + os.environ.get("PATH", "")
    os.environ["NPM_CONFIG_CACHE"] = str(Path(tempfile.gettempdir()) / "npm-cache")
    executable = shutil.which(name)
    if not executable:
        subprocess.check_call(
            [shutil.which("npm") or "npm", "install", "-g", "--prefix", str(npm_prefix), package]
        )
        executable = shutil.which(name)
        if not executable:
            raise RuntimeError(f"{name} was not found after npm installation")
    return executable


def terminal_tty():
    try:
        return os.ttyname(sys.stdin.fileno())
    except (AttributeError, OSError, ValueError):
        return ""


def sandbox_command(command, *, agent_home, gpu_env, broker=None):
    """Confine the whole agent process, including its tools and hooks."""
    bwrap = shutil.which("bwrap")
    if not bwrap:
        raise RuntimeError("Install bubblewrap before running an agent on Linux")
    workspace = Path.cwd().resolve()
    if workspace == Path.home().resolve() or str(workspace) in {
        "/", "/home", "/root", "/tmp", "/run", "/var", "/proc", "/dev",
        "/sys", "/etc", "/usr", "/bin", "/sbin", "/lib", "/lib64",
    } or any(workspace.is_relative_to(path) for path in ("/proc", "/dev", "/sys", "/run")):
        raise RuntimeError("Choose a project directory, not home or a system directory")
    agent_home = Path(agent_home).resolve()
    agent_home.mkdir(parents=True, exist_ok=True)
    # Isolate processes, drop capabilities, share network.
    # Host files remain readable so installed tools and launcher paths still work.
    # Keep /tmp and /run private so host sockets stay outside the sandbox.
    sandbox = [
        bwrap, "--unshare-all", "--share-net", "--die-with-parent",
        "--new-session", "--cap-drop", "ALL", "--ro-bind", "/", "/",
        "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
        "--tmpfs", "/run",
    ]
    # Keep GPU devices hidden unless the wrapper opts in.
    if os.environ.get(gpu_env) == "1":
        for path in (Path("/dev/dri"), *sorted(Path("/dev").glob("nvidia*"))):
            if path.exists() and (path.is_dir() or path.is_char_device()):
                sandbox.extend(["--dev-bind", str(path), str(path)])
    for path in (workspace, agent_home, *WRITABLE_ROOTS):
        if path.exists():
            sandbox.extend(["--bind", str(path), str(path)])
    if broker is not None:
        sandbox.extend(["--ro-bind", str(broker.endpoint), MOUNT_PATH])
        if (broker.endpoint / "title.sock").exists():
            sandbox.extend(["--setenv", SOCKET_ENV, MOUNT_PATH + "/title.sock"])
    sandbox.extend(["--setenv", "TMPDIR", "/tmp", "--chdir", str(workspace), "--"])
    return sandbox + command

def run_cli(command, *, title, agent_home, gpu_env, use_external_sandbox):
    set_terminal_title(title)
    if sys.platform == "win32":
        return subprocess.call(command)
    if use_external_sandbox:
        with HostCommandBroker() as broker:
            tty = terminal_tty()
            relay = TerminalTitleRelay(broker.endpoint / "title.sock", tty) if tty else nullcontext()
            with relay:
                return subprocess.call(sandbox_command(
                    command, agent_home=agent_home, gpu_env=gpu_env, broker=broker
                ))
    os.execv(command[0], command)
