#!/usr/bin/env bash
set -euo pipefail

if (( $# == 0 )); then
    echo "Usage: $(basename "$0") <transcription>" >&2
    exit 2
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
transcription="$*"
codex_script="$script_dir/../scripts/r/codex.sh"

exec bash "$script_dir/start_script" \
    --run-in-tmux \
    "$codex_script" -- -- "$transcription"
