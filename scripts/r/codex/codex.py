import fnmatch
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

from utils.term import set_terminal_title


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
        'tui.alternate_screen="always"',
        'tui.fullscreen_transcript=false',
        'tui.terminal_title=[]',
        'tui.status_line=["model","context-used","used-tokens","weekly-limit"]',
        'tui.show_tooltips=false',
        'tui.keymap.global.open_transcript=["ctrl-t","page-up"]',
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
    config.append("developer_instructions=" + json.dumps(developer_instructions))

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
    if fnmatch.fnmatch(process_root, "*/com.termux/files/usr/var/lib/proot-distro/containers/*/rootfs"):
        command = [codex, "--dangerously-bypass-approvals-and-sandbox"]
    else:
        command = [codex, "--sandbox", "workspace-write", "--ask-for-approval", "on-request"]
        downloads = str(Path.home() / "Downloads")
        android_home = str(Path.home() / ".android")
        config += [
            'approvals_reviewer="user"',
            'sandbox_workspace_write.network_access=true',
            "sandbox_workspace_write.writable_roots=["
            + ",".join([json.dumps(downloads), json.dumps(android_home)])
            + "]",
        ]

    try:
        os.environ["CODEX_TERMINAL_TTY"] = os.ttyname(sys.stdin.fileno())
    except (AttributeError, OSError, ValueError):
        os.environ["CODEX_TERMINAL_TTY"] = ""
    for event, status in [("UserPromptSubmit", "⧗"), ("Stop", "✓")]:
        config.append(
            f"hooks.{event}="
            + '[{hooks=[{type="command",command='
            + json.dumps(hook_command(status))
            + ',timeout=5}]}]'
        )
    for value in config:
        command.extend(["-c", value])
    command.extend(args)

    set_terminal_title("Codex (new)")
    if sys.platform == "win32":
        return subprocess.call(command)
    os.execv(codex, command)


if __name__ == "__main__":
    raise SystemExit(main())
