import fnmatch
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

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
    config = [
        'model_verbosity="low"',
        'tui.alternate_screen="never"',
        'tui.fullscreen_transcript=false',
        'tui.terminal_title=[]',
        'tui.status_line=["context-used","used-tokens","weekly-limit"]',
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
            config.append("developer_instructions=" + json.dumps(args[1]))
        args = args[2:]

    os.chdir(Path(__file__).resolve().parents[3])
    if os.environ.get("CODEX_PROJECT_DIR"):
        os.chdir(os.environ["CODEX_PROJECT_DIR"])

    npm_prefix = Path.home() / ".npm-global"
    npm_bin = npm_prefix if sys.platform == "win32" else npm_prefix / "bin"
    os.environ["PATH"] = str(npm_bin) + os.pathsep + os.environ.get("PATH", "")
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
        config += ['approvals_reviewer="auto_review"', 'sandbox_workspace_write.network_access=true']

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
