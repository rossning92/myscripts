import fnmatch
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

from utils.host_command_broker import CLIENT_PATH, MOUNT_PATH, HostCommandBroker
from utils.term import set_terminal_title
from utils.term.title import SOCKET_ENV, TerminalTitleRelay

WRITABLE_ROOTS = (
    Path.home() / ".android",
    Path.home() / ".gradle",
    Path.home() / ".cache" / "uv",
    Path.home() / ".config" / "godot",
    Path.home() / ".cache" / "godot",
    Path.home() / ".local" / "share" / "godot",
)


def hook_command(status):
    args = [sys.executable, str(Path(__file__).with_name("terminal_title_hook.py")), status]
    if sys.platform != "win32":
        return shlex.join(args)

    # PowerShell restores the title after native programs exit, so apply it there.
    args.append("--print-title")
    command = "$result = & " + " ".join("'" + arg.replace("'", "''") + "'" for arg in args)
    command += "; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"
    command += "; if ($result) { $Host.UI.RawUI.WindowTitle = ($result | ConvertFrom-Json).terminal_title }"
    return command + "; '{}'"


def sandbox_command(command, broker=None):
    """Confine the whole Codex process, including its tools and hooks."""
    bwrap = shutil.which("bwrap")
    if not bwrap:
        raise RuntimeError("Install bubblewrap before running Codex on Linux")
    workspace = Path.cwd().resolve()
    if workspace == Path.home().resolve() or str(workspace) in {
        "/", "/home", "/root", "/tmp", "/run", "/var", "/proc", "/dev",
        "/sys", "/etc", "/usr", "/bin", "/sbin", "/lib", "/lib64",
    } or any(workspace.is_relative_to(path) for path in ("/proc", "/dev", "/sys", "/run")):
        raise RuntimeError("Choose a project directory, not home or a system directory")
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).resolve()
    codex_home.mkdir(parents=True, exist_ok=True)
    # Isolate processes, drop capabilities, share network.
    # Host files remain readable so installed tools and launcher paths still work.
    # Private /tmp and /run hide host sockets and temporary files.
    sandbox = [
        bwrap, "--unshare-all", "--share-net", "--die-with-parent",
        "--new-session", "--cap-drop", "ALL", "--ro-bind", "/", "/",
        "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
        "--tmpfs", "/run",
    ]
    # Opt in at launch with CODEX_GPU=1; keep GPU devices hidden by default.
    if os.environ.get("CODEX_GPU") == "1":
        for path in (Path("/dev/dri"), *sorted(Path("/dev").glob("nvidia*"))):
            if path.exists() and (path.is_dir() or path.is_char_device()):
                sandbox.extend(["--dev-bind", str(path), str(path)])
    for path in (workspace, codex_home, *WRITABLE_ROOTS):
        if path.exists():
            sandbox.extend(["--bind", str(path), str(path)])
    if broker is not None:
        sandbox.extend(["--ro-bind", str(broker.endpoint), MOUNT_PATH])
        sandbox.extend(["--setenv", SOCKET_ENV, MOUNT_PATH + "/title.sock"])
    sandbox.extend(["--setenv", "TMPDIR", "/tmp", "--chdir", str(workspace), "--"])
    return sandbox + command


def main():
    args = sys.argv[1:]
    developer_instructions = (
        "Skills under ~/.codex/skills/ may be symlinks into the current workspace. "
        "When asked to update one, resolve the link and edit it directly without "
        "asking for permission.\n\n"
        "You were launched through the myscripts Codex wrapper. Check "
        "scripts/r/codex/codex.py for wrapper-provided configuration before "
        "changing global Codex settings."
    )
    config = [
        'model_verbosity="low"',
        'hide_agent_reasoning=true',
        'tui.alternate_screen="always"',
        'tui.fullscreen_transcript=false',
        'tui.terminal_title=[]',
        'tui.status_line=["model","used-tokens","weekly-limit"]',
        'tui.show_tooltips=false',
        'check_for_update_on_startup=false',
        'features.hooks=true',
    ]
    if args[:1] == ["--context"]:
        if len(args) < 2:
            sys.stderr.write("--context requires a value\n")
            return 2
        if args[1]:
            developer_instructions += "\n\n" + args[1]
        args = args[2:]

    os.chdir(Path(__file__).resolve().parents[3])
    if os.environ.get("CODEX_PROJECT_DIR"):
        os.chdir(os.environ["CODEX_PROJECT_DIR"])

    npm_prefix = Path.home() / ".npm-global"
    npm_bin = npm_prefix if sys.platform == "win32" else npm_prefix / "bin"
    os.environ["PATH"] = str(npm_bin) + os.pathsep + os.environ.get("PATH", "")
    os.environ["NPM_CONFIG_CACHE"] = str(Path(tempfile.gettempdir()) / "npm-cache")
    # Codex sanitizes PATH for shell commands, so preserve the launcher's PATH
    # and npm cache to keep myscripts tools available without writing to ~/.npm.
    config.append(
        "shell_environment_policy.set.PATH=" + json.dumps(os.environ["PATH"])
    )
    config.append(
        "shell_environment_policy.set.NPM_CONFIG_CACHE="
        + json.dumps(os.environ["NPM_CONFIG_CACHE"])
    )
    codex = shutil.which("codex")
    if not codex:
        subprocess.check_call(
            [shutil.which("npm") or "npm", "install", "-g", "--prefix", str(npm_prefix), "@openai/codex"]
        )
        codex = shutil.which("codex")
        if not codex:
            raise RuntimeError("Codex was not found after npm installation")

    try:
        process_root = os.readlink("/proc/self/root")
    except OSError:
        process_root = ""
    use_external_sandbox = sys.platform == "linux" and not fnmatch.fnmatch(
        process_root, "*/com.termux/files/usr/var/lib/proot-distro/containers/*/rootfs"
    )
    if use_external_sandbox:
        command = [codex, "--dangerously-bypass-approvals-and-sandbox"]
        developer_instructions += (
            "\n\nYou run inside Bubblewrap. For a command that needs host access, use "
            f'{CLIENT_PATH} --reason "why host access is needed" '
            '-- command arg... . The host opens an approval pane in the originating tmux window. '
            "Never approve your own request or interact with the approval pane. "
            "Each request needs approval; denial means do not retry without new user direction. "
            "Use --timeout SECONDS before -- for commands longer than 300 seconds (max 3600). "
            "Shell syntax requires an explicit bash -c argument. Host commands have no interactive stdin."
        )
    else:
        command = [codex, "--sandbox", "workspace-write", "--ask-for-approval", "on-request"]
        config += [
            'approvals_reviewer="user"',
            'sandbox_workspace_write.network_access=true',
            "sandbox_workspace_write.writable_roots="
            + json.dumps([str(path) for path in WRITABLE_ROOTS]),
        ]
    config.append("developer_instructions=" + json.dumps(developer_instructions))

    try:
        os.environ["CODEX_TERMINAL_TTY"] = os.ttyname(sys.stdin.fileno())
    except (AttributeError, OSError, ValueError):
        os.environ["CODEX_TERMINAL_TTY"] = ""
    for event, status, matcher in [
        ("UserPromptSubmit", "⧗", None),
        ("Stop", "✓", None),
        ("PermissionRequest", "‽", None),
        ("PreToolUse", "‽", "(^|.*__)request_user_input(_async)?$"),
        ("PostToolUse", "⧗", None),
    ]:
        config.append(
            f"hooks.{event}="
            + '[{'
            + ("matcher=" + json.dumps(matcher) + "," if matcher else "")
            + 'hooks=[{type="command",command='
            + json.dumps(hook_command(status))
            + ',timeout=5}]}]'
        )
    # Wrapper overrides require embedded mode; select it explicitly to avoid
    # the shared-server fallback warning without changing the user's config.
    command.append("--no-daemon")
    for value in config:
        command.extend(["-c", value])
    command.extend(args)

    set_terminal_title("Codex (new)")
    if sys.platform == "win32":
        return subprocess.call(command)
    if use_external_sandbox:
        with HostCommandBroker() as broker:
            with TerminalTitleRelay(
                broker.endpoint / "title.sock", os.environ["CODEX_TERMINAL_TTY"] or "/dev/tty"
            ):
                return subprocess.call(sandbox_command(command, broker))
    os.execv(command[0], command)


if __name__ == "__main__":
    raise SystemExit(main())
