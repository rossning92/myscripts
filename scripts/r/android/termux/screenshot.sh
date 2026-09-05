#!/usr/bin/env bash
set -euo pipefail

output="/storage/emulated/0/Pictures/Screenshots/screenshot_$(date +%Y%m%d_%H%M%S).png"

rish -c '
out=$1
mkdir -p "$(dirname "$out")"
screencap -p "$out"
if [ ! -s "$out" ]; then
    echo "Failed to create screenshot: $out" >&2
    exit 1
fi
' sh "$output"

printf '%s\n' "$output"
termux-toast "Screenshot captured" || true
