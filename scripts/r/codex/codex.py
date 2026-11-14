import json
import os
from pathlib import Path
import shlex
import sys

from utils.agent_cli import (
    HOST_ACCESS_INSTRUCTIONS,
    WRITABLE_ROOTS,
    external_sandbox_enabled,
    prepare_cli,
    run_cli,
    take_context,
    terminal_tty,
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


def main():
    try:
        context, args = take_context(sys.argv[1:])
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
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
    if context:
        developer_instructions += "\n\n" + context

    codex = prepare_cli("codex", "@openai/codex", project_dir_env="CODEX_PROJECT_DIR")
    # Codex sanitizes PATH for shell commands, so preserve the launcher's PATH
    # and npm cache to keep myscripts tools available without writing to ~/.npm.
    config.append(
        "shell_environment_policy.set.PATH=" + json.dumps(os.environ["PATH"])
    )
    config.append(
        "shell_environment_policy.set.NPM_CONFIG_CACHE="
        + json.dumps(os.environ["NPM_CONFIG_CACHE"])
    )
    use_external_sandbox = external_sandbox_enabled()
    if use_external_sandbox:
        command = [codex, "--dangerously-bypass-approvals-and-sandbox"]
        developer_instructions += "\n\n" + HOST_ACCESS_INSTRUCTIONS
    else:
        command = [codex, "--sandbox", "workspace-write", "--ask-for-approval", "on-request"]
        config += [
            'approvals_reviewer="user"',
            'sandbox_workspace_write.network_access=true',
            "sandbox_workspace_write.writable_roots="
            + json.dumps([str(path) for path in WRITABLE_ROOTS]),
        ]
    config.append("developer_instructions=" + json.dumps(developer_instructions))

    os.environ["CODEX_TERMINAL_TTY"] = terminal_tty()
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

    return run_cli(
        command,
        title="Codex (new)",
        agent_home=os.environ.get("CODEX_HOME", str(Path.home() / ".codex")),
        gpu_env="CODEX_GPU",
        use_external_sandbox=use_external_sandbox,
    )


if __name__ == "__main__":
    raise SystemExit(main())
