#!/bin/bash
set -e

ROOT_DIR="$(realpath "$(dirname "$0")/../../")"

if [ -d "$ROOT_DIR/scripts/r/videoedit/movy" ]; then
    if (cd "$ROOT_DIR/scripts/r/videoedit/movy" && git diff --quiet); then
        echo "Update submodule movy..."
        (cd "$ROOT_DIR" && git submodule update --recursive --remote || true)
    else
        echo "(Skip updating submodule movy - working tree is dirty.)"
    fi
fi
