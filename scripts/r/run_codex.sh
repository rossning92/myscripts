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

# Run without filesystem sandboxing and use the configured approval policy.
codex_args=(--sandbox danger-full-access)

if is_termux_proot_distro; then
    codex_args=(--dangerously-bypass-approvals-and-sandbox)
fi

exec codex "${codex_args[@]}" "$@"
