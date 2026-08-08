#!/usr/bin/env bash
set -euo pipefail

dpi="${SCAN_DPI:-300}"
scan_format="${SCAN_FORMAT:-jpg}"

case "$scan_format" in
jpg | jpeg)
    scan_format="jpg"
    output_format="jpeg"
    ;;
tif | tiff)
    scan_format="tif"
    output_format="tiff"
    ;;
png | pnm | pdf)
    output_format="$scan_format"
    ;;
*)
    printf 'Unsupported scan format: %s\n' "$scan_format" >&2
    exit 1
    ;;
esac

if [[ $# -gt 0 ]]; then
    output_file="$1"
    mkdir -p "$(dirname "$output_file")"

    if [[ -z "${SCAN_FORMAT:-}" ]]; then
        case "${output_file##*.}" in
        jpg | jpeg)
            output_format="jpeg"
            ;;
        tif | tiff)
            output_format="tiff"
            ;;
        *)
            output_format="${output_file##*.}"
            ;;
        esac
    fi
else
    output_dir="$HOME/Scans"
    mkdir -p "$output_dir"
    output_file="$output_dir/scan_$(date +%Y%m%d_%H%M%S).$scan_format"
fi

scanner_device="$(scanimage -L | sed -n "s/^device [\`']\([^']*\)'.*/\1/p" | grep -v '^v4l:' | head -n 1)"

if [[ -z "$scanner_device" ]]; then
    printf 'No scanner found\n' >&2
    exit 1
fi

scan_args=(
    --output-file "$output_file"
    --format="$output_format"
    --progress
    -d "$scanner_device"
    --resolution "${dpi}dpi"
)

if [[ -n "${SCAN_WIDTH:-}" ]]; then
    scan_args+=(-x "$SCAN_WIDTH")
fi

if [[ -n "${SCAN_HEIGHT:-}" ]]; then
    scan_args+=(-y "$SCAN_HEIGHT")
fi

scanimage "${scan_args[@]}"

if [[ -n "${SCAN_AUTO_CROP:-}" ]]; then
    run_script r/image/auto_crop_image.py "$output_file" --inplace
fi

printf 'Saved scan to %s\n' "$output_file"

if [[ -n "${SCAN_AUTO_OPEN:-}" ]]; then
    xdg-open "$output_file"
fi
