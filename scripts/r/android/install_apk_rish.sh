#!/usr/bin/env bash
set -euo pipefail

APK=${1:?Usage: install_apk_rish.sh APK PACKAGE}
PACKAGE=${2:?Usage: install_apk_rish.sh APK PACKAGE}
RISH="${RISH:-rish}"

if [[ ! -f "$APK" ]]; then
    echo "APK not found: $APK" >&2
    exit 1
fi
if ! command -v "$RISH" >/dev/null 2>&1; then
    echo "rish is missing or not executable: $RISH" >&2
    exit 1
fi

if [[ ! "$PACKAGE" =~ ^[A-Za-z0-9_.]+$ ]]; then
    echo "Invalid Android package name: $PACKAGE" >&2
    exit 1
fi

APK_SIZE=$(stat -c %s "$APK")
"$RISH" -c "pm install -r --user 0 -S $APK_SIZE" < "$APK"
"$RISH" -c "am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -p $PACKAGE"
