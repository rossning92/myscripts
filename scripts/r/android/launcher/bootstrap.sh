#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
MYSCRIPTS_DIR=$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)
PROJECT_DIR=${LAUNCHER_DIR:-"$MYSCRIPTS_DIR/repos/launcher"}

if [[ -d "$PROJECT_DIR/.git" ]]; then
    echo "Launcher repository already exists: $PROJECT_DIR"
    exit 0
fi

if [[ -e "$PROJECT_DIR" ]]; then
    echo "Cannot clone Launcher: path exists but is not a Git repository: $PROJECT_DIR" >&2
    exit 1
fi

mkdir -p "$(dirname -- "$PROJECT_DIR")"
gh repo clone rossning92/launcher "$PROJECT_DIR"
echo "Launcher repository cloned: $PROJECT_DIR"
