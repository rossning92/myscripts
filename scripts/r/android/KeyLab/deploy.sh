#!/bin/bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$SCRIPT_DIR"

# shellcheck source=../android_helper.sh
source "$SCRIPT_DIR/../android_helper.sh"

APK_PATH=${APK_PATH:-app/build/outputs/apk/debug/app-debug.apk}
PACKAGE_NAME=${PACKAGE_NAME:-com.ross.keylab}
ACCESSIBILITY_SERVICE=${ACCESSIBILITY_SERVICE:-$PACKAGE_NAME/.LongPressAccessibilityService}
MAIN_ACTIVITY=${MAIN_ACTIVITY:-$PACKAGE_NAME/.MainActivity}

run_script "$SCRIPT_DIR/build.sh"

android_install_apk "$APK_PATH"

# Enable the accessibility service (intercepts hardware keys).
enabled_services=$(android_shell \
    "settings get secure enabled_accessibility_services" | tr -d '\r')
if [[ "$enabled_services" != *"$ACCESSIBILITY_SERVICE"* ]]; then
    if [[ -z "$enabled_services" || "$enabled_services" == "null" ]]; then
        android_shell \
            "settings put secure enabled_accessibility_services '$ACCESSIBILITY_SERVICE'"
    else
        android_shell \
            "settings put secure enabled_accessibility_services '$enabled_services:$ACCESSIBILITY_SERVICE'"
    fi
fi
android_shell "settings put secure accessibility_enabled 1"

android_shell "appops set '$PACKAGE_NAME' WRITE_SETTINGS allow"
android_shell "settings put secure accessibility_sticky_keys 1"
android_shell "am start -n '$MAIN_ACTIVITY'"
