#!/usr/bin/env bash
set -euo pipefail

output="/storage/emulated/0/Pictures/Screenshots/selected_app_$(date +%Y%m%d_%H%M%S).png"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if command -v termux-toast >/dev/null 2>&1; then
    termux-toast "Choose an app from Recents" || true
fi

run_script "$script_dir/../rish.sh" -c '
out=$1
timeout=$2
mkdir -p "$(dirname "$out")"

current_component() {
    line=$(dumpsys window | grep "mCurrentFocus=" | head -n 1)
    set -- $line
    printf "%s\n" "$3" | cut -d "}" -f 1
}

home_package=$(cmd package resolve-activity --brief \
    -a android.intent.action.MAIN \
    -c android.intent.category.HOME 2>/dev/null | tail -n 1 | cut -d/ -f1)

deadline=$(($(date +%s) + timeout))
input keyevent KEYCODE_APP_SWITCH
recents_component=

while [ "$(date +%s)" -lt "$deadline" ]; do
    if dumpsys activity activities | grep -q "topDisplayFocusedRootTask=.*type=recents"; then
        recents_component=$(current_component)
        break
    fi
    sleep 0.25
done

if [ -z "$recents_component" ]; then
    echo "Could not open the Recents screen" >&2
    exit 1
fi

trap "input keyevent --doubletap KEYCODE_APP_SWITCH" EXIT

selected_component=
stable_count=0
while [ "$(date +%s)" -lt "$deadline" ]; do
    component=$(current_component)
    case "$component" in
        ""|com.termux/*|com.android.systemui/*|"$home_package"/*|"$recents_component")
            selected_component=
            stable_count=0
            ;;
        *)
            if [ "$component" = "$selected_component" ]; then
                stable_count=$((stable_count + 1))
            else
                selected_component=$component
                stable_count=1
            fi
            if [ "$stable_count" -ge 2 ]; then
                break
            fi
            ;;
    esac
    sleep 0.25
done

if [ "$stable_count" -lt 2 ]; then
    echo "Timed out waiting for an app to be selected" >&2
    exit 1
fi

sleep 1
screencap -p "$out"
if [ ! -s "$out" ]; then
    echo "Failed to create screenshot: $out" >&2
    exit 1
fi
' sh "$output" 15

printf '%s\n' "$output"
