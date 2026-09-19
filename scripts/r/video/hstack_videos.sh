#!/usr/bin/env bash

set -euo pipefail

output=output.mp4
if [[ ${1:-} == -o || ${1:-} == --output ]]; then
    output=$2
    shift 2
fi

if (($# < 2)); then
    echo "Usage: run_script r/video/hstack_videos.sh [-o OUTPUT.mp4] VIDEO1 VIDEO2 [VIDEO ...]" >&2
    exit 2
fi

inputs=()
for video in "$@"; do
    inputs+=(-i "$video")
done

ffmpeg -hide_banner -y "${inputs[@]}" \
    -filter_complex "hstack=inputs=$#[v]" \
    -map "[v]" -map 0:a:0 \
    -c:v libx264 -crf 23 -preset veryfast \
    -c:a copy "$output"
