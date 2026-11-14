import os
from pathlib import Path
import shutil
import sys

from utils.agent_cli import (
    HOST_ACCESS_INSTRUCTIONS,
    external_sandbox_enabled,
    prepare_cli,
    run_cli,
    take_context,
)


def main():
    try:
        context, args = take_context(sys.argv[1:])
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2

    claude = prepare_cli(
        "claude", "@anthropic-ai/claude-code", project_dir_env="CLAUDE_PROJECT_DIR"
    )
    use_external_sandbox = external_sandbox_enabled()
    claude_home = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude").resolve()
    instructions = (
        "You were launched through the myscripts Claude wrapper. Check "
        "scripts/r/claude/claude.py and libs/utils/agent_cli.py for wrapper-provided "
        "configuration before changing global Claude settings."
    )
    if context:
        instructions += "\n\n" + context
    command = [claude]
    if use_external_sandbox:
        # An explicit config directory keeps .claude.json and its atomic writes
        # inside the writable mount. Seed existing account and project settings.
        claude_home.mkdir(parents=True, exist_ok=True)
        legacy_config = Path.home() / ".claude.json"
        config = claude_home / ".claude.json"
        if not os.environ.get("CLAUDE_CONFIG_DIR") and legacy_config.exists() and not config.exists():
            shutil.copy2(legacy_config, config)
        os.environ["CLAUDE_CONFIG_DIR"] = str(claude_home)
        os.environ["DISABLE_AUTOUPDATER"] = "1"
        command.append("--dangerously-skip-permissions")
        instructions += "\n\n" + HOST_ACCESS_INSTRUCTIONS
    command.extend(["--append-system-prompt", instructions, *args])
    return run_cli(
        command,
        title="Claude (new)",
        agent_home=claude_home,
        gpu_env="CLAUDE_GPU",
        use_external_sandbox=use_external_sandbox,
    )


if __name__ == "__main__":
    raise SystemExit(main())
