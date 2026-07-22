#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

APK="app/build/outputs/apk/debug/app-debug.apk"
PACKAGE="com.ross.speechtotext"

run_script ./build.sh

if [[ -n "${TERMUX_VERSION:-}" || "${PREFIX:-}" == /data/data/com.termux/files/usr ]]; then
    RISH="${RISH:-../rish.sh}"
    if [[ ! -x "$RISH" ]]; then
        echo "rish is missing or not executable: $RISH" >&2
        exit 1
    fi

    device_shell() {
        "$RISH" -c "$1"
    }

    APK_SIZE=$(stat -c %s "$APK")
    "$RISH" -c "pm install -r --user 0 -S $APK_SIZE" < "$APK"
else
    device_shell() {
        adb shell "$1"
    }

    adb install -r --user 0 "$APK"
fi

# Force-stop before enabling accessibility below: it clears the enabled service.
if [[ -n "${OPENAI_API_KEY:-}" ]]; then
    PREFS="/data/data/$PACKAGE/shared_prefs/${PACKAGE}_preferences.xml"
    device_shell "am force-stop $PACKAGE"
    printf "<?xml version='1.0' encoding='utf-8' standalone='yes' ?>\n<map>\n    <string name=\"openai_api_key\">%s</string>\n</map>\n" "$OPENAI_API_KEY" |
        device_shell "run-as $PACKAGE sh -c 'cat > $PREFS'"
    echo "OpenAI API key set (${#OPENAI_API_KEY} chars)"
else
    echo "OPENAI_API_KEY not set - skipping API key injection"
fi

device_shell "appops set $PACKAGE SYSTEM_ALERT_WINDOW allow"
device_shell "pm grant $PACKAGE android.permission.RECORD_AUDIO"
device_shell "pm grant $PACKAGE android.permission.POST_NOTIFICATIONS"
# Lets the app swap the active keyboard for its silent IME while dictating.
device_shell "pm grant $PACKAGE android.permission.WRITE_SECURE_SETTINGS"

# Enable the silent IME so the app can switch to it.
device_shell "ime enable $PACKAGE/.SilentIme"

# Enable the accessibility service without duplicating it.
ENABLED=$(device_shell "settings get secure enabled_accessibility_services" | tr -d '\r')
SVC="$PACKAGE/$PACKAGE.TypeAccessibilityService"
if [[ "$ENABLED" != *"$SVC"* ]]; then
    if [[ -z "$ENABLED" || "$ENABLED" == "null" ]]; then
        device_shell "settings put secure enabled_accessibility_services '$SVC'"
    else
        device_shell "settings put secure enabled_accessibility_services '$ENABLED:$SVC'"
    fi
fi
device_shell "settings put secure accessibility_enabled 1"

device_shell "am start -n $PACKAGE/.MainActivity"
