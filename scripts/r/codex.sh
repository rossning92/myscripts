#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
title_hook_path="$script_dir/codex_terminal_title_hook.py"

# Sessions launched before the hook was split out still call this entry point.
if [[ "${1:-}" == "--terminal-title-hook" ]]; then
    shift
    exec python "$title_hook_path" "$@"
fi

cd "$script_dir/../.."

if [[ -n "${CODEX_PROJECT_DIR:-}" ]]; then
    cd "$CODEX_PROJECT_DIR"
fi

if ! command -v codex >/dev/null 2>&1; then
    npm install -g @openai/codex
fi

is_termux_proot_distro() {
    local process_root

    process_root="$(readlink /proc/self/root 2>/dev/null)" || return 1
    [[ "$process_root" == */com.termux/files/usr/var/lib/proot-distro/containers/*/rootfs ]]
}

if is_termux_proot_distro; then
    sandbox_args=(--dangerously-bypass-approvals-and-sandbox)
else
    sandbox_args=(--sandbox danger-full-access)
fi

codex_args=(
    "${sandbox_args[@]}"
    -c 'tui.terminal_title=[]'
    -c 'tui.status_line=["context-used","weekly-limit"]'
    -c 'tui.show_tooltips=false'
    -c 'tui.keymap.global.open_transcript=["ctrl-t","page-up"]'
    -c 'check_for_update_on_startup=false'
)

hook_command_toml() {
    python -c 'import json, shlex, sys; print(json.dumps(shlex.join(sys.argv[1:])))' \
        python "$title_hook_path" "$1"
}

working_hook_toml="$(hook_command_toml '⧗')"
ready_hook_toml="$(hook_command_toml '✓')"
codex_args+=(
    -c 'features.hooks=true'
    -c "hooks.UserPromptSubmit=[{hooks=[{type=\"command\",command=$working_hook_toml,timeout=5}]}]"
    -c "hooks.Stop=[{hooks=[{type=\"command\",command=$ready_hook_toml,timeout=5}]}]"
)

if [[ "${1:-}" == "--context" ]]; then
    [[ -n "${2+x}" ]] || {
        echo "--context requires a value" >&2
        exit 2
    }
    if [[ -n "$2" ]]; then
        codex_args+=(-c "developer_instructions=$2")
    fi
    shift 2
fi

# The hooks do not run until the first prompt is submitted, so provide a useful
# title while Codex is initially idle.
{ printf '\033]0;Codex (new)\007' >/dev/tty; } 2>/dev/null || true

exec codex "${codex_args[@]}" "$@"
