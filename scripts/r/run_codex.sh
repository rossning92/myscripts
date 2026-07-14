#!/usr/bin/env bash

if [[ -n "${CODEX_PROJECT_DIR:-}" ]]; then
    cd "$CODEX_PROJECT_DIR" || exit
fi

exec codex "$@"
