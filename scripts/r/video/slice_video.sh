#!/bin/bash
f="$1"
t="${SEGMENT_TIME:-20}"
d="${f%.*}_parts"
mkdir -p "$d"
ffmpeg -i "$f" -f segment -segment_time "$t" -reset_timestamps 1 -r 25 -c:v libx264 -crf 23 -c:a aac -force_key_frames "expr:gte(t,n_forced*$t)" "$d/%03d.mp4"
