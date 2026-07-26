#!/usr/bin/env bash

ANDROID_HELPER_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

android_is_local_device() {
    [[ -n "${TERMUX_VERSION:-}" || "${PREFIX:-}" == /data/data/com.termux/files/usr ]]
}

android_require_rish() {
    RISH="${RISH:-$ANDROID_HELPER_DIR/rish.sh}"
    if [[ ! -x "$RISH" ]]; then
        echo "rish is missing or not executable: $RISH" >&2
        return 1
    fi
}

android_install_apk() {
    local apk="$1"

    if [[ ! -f "$apk" ]]; then
        echo "APK not found: $apk" >&2
        return 1
    fi

    if android_is_local_device; then
        android_require_rish
        local apk_size
        apk_size=$(stat -c %s "$apk")
        "$RISH" -c "pm install -r --user 0 -S $apk_size" < "$apk"
    else
        adb install -r --user 0 "$apk"
    fi
}

android_shell() {
    local command="$1"

    if android_is_local_device; then
        android_require_rish
        "$RISH" -c "$command"
    else
        adb shell "$command"
    fi
}
