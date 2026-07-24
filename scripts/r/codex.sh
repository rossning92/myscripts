#!/usr/bin/env bash

cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit

if [[ -n "${CODEX_PROJECT_DIR:-}" ]]; then
    cd "$CODEX_PROJECT_DIR" || exit
fi

if ! command -v codex >/dev/null 2>&1; then
    npm install -g @openai/codex || exit
fi

is_termux_proot_distro() {
    local process_root

    process_root="$(readlink /proc/self/root 2>/dev/null)" || return 1
    [[ "$process_root" == */com.termux/files/usr/var/lib/proot-distro/containers/*/rootfs ]]
}

codex_args=(
    --sandbox danger-full-access
    -c 'tui.terminal_title=["activity","app-name","project"]'
    -c 'tui.status_line=["context-used","weekly-limit"]'
    -c 'tui.animations=false'
    -c 'tui.show_tooltips=false'
    -c 'check_for_update_on_startup=false'
)

if is_termux_proot_distro; then
    codex_args=(
        --dangerously-bypass-approvals-and-sandbox
        -c 'tui.terminal_title=["activity","app-name","project"]'
        -c 'tui.status_line=["context-used","weekly-limit"]'
        -c 'tui.animations=false'
        -c 'tui.show_tooltips=false'
        -c 'check_for_update_on_startup=false'
    )
fi

if [[ "${1:-}" == "--context" ]]; then
    [[ -n "${2+x}" ]] || { echo "--context requires a value" >&2; exit 2; }
    codex_args+=(-c "developer_instructions=$2")
    shift 2
fi

exec codex "${codex_args[@]}" "$@"
