#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

if [[ $# != 1 ]]; then
    echo 'Usage: clip_image.sh OUTPUT' >&2
    exit 2
fi
if ! command -v termux-saf-read >/dev/null || ! command -v file >/dev/null; then
    echo 'Install the required commands with: pkg install termux-api file' >&2
    exit 1
fi

destination=$1
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
reader="$script_dir/clipboard-uri.jar"
if [[ ! -r $reader ]]; then
    echo "Missing $reader. Build it with the sibling build.sh." >&2
    exit 1
fi
work_dir=$(mktemp -d)
temporary=
cleanup() {
    rm -rf -- "$work_dir"
    if [[ -n $temporary ]]; then rm -f -- "$temporary"; fi
}
trap cleanup EXIT

# Android requires dynamically loaded DEX files to be read-only.
install -m 400 "$reader" "$work_dir/clipboard-uri.jar"
uri=$(CLASSPATH="$work_dir/clipboard-uri.jar" /system/bin/app_process /system/bin ReadClipboardUri)
temporary=$(mktemp -- "$(dirname -- "$destination")/.clipboard-image.XXXXXXXX")
timeout 30 termux-saf-read "$uri" > "$temporary"
if [[ $(file -b --mime-type -- "$temporary") != image/* ]]; then
    echo 'The clipboard item could not be read as an image.' >&2
    exit 1
fi
mv -fT -- "$temporary" "$destination"
printf '%s\n' "$destination"
