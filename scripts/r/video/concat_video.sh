#!/bin/bash
set -e

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 file1.mp4 file2.mp4 ..."
    exit 1
fi

OUTPUT="output.mp4"

# Create a temporary file list
FILELIST=$(mktemp)
for f in "$@"; do
    # Use absolute path to avoid issues with concat demuxer
    ABS_PATH=$(realpath "$f")
    echo "file '$ABS_PATH'" >> "$FILELIST"
done

echo "Concatenating files into $OUTPUT..."
ffmpeg -y -f concat -safe 0 -i "$FILELIST" -c copy "$OUTPUT"

rm "$FILELIST"
echo "Done -> $OUTPUT"
