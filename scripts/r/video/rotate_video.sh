#!/bin/bash
set -e

[[ "$ROTATE_ANGLE_CW" == "180" ]] && VF="transpose=1,transpose=1"
[[ "$ROTATE_ANGLE_CW" == "270" ]] && VF="transpose=2"
VF="${VF:-transpose=1}"

mkdir -p out
for f in "$@"; do
    ffmpeg -i "$f" -vf "$VF" -c:v libx264 -crf 18 -c:a copy "out/${f##*/}"
done
