#!/usr/bin/env bash

if [[ -n "${CODEX_PROJECT_DIR:-}" ]]; then
    cd "$CODEX_PROJECT_DIR" || exit
fi

if ! command -v codex >/dev/null 2>&1; then
    npm install -g @openai/codex || exit
fi

exec codex "$@"
