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

if [[ -n "${OPENAI_API_KEY:-}" ]]; then
    RESULT=$(device_shell "am broadcast -n $PACKAGE/.ConfigReceiver \
        -a $PACKAGE.action.SET_OPENAI_API_KEY \
        --es openai_api_key '$OPENAI_API_KEY'")
    if [[ "$RESULT" != *"result=0"* ]]; then
        echo "Failed to configure OpenAI API key: $RESULT" >&2
        exit 1
    fi
    echo "OpenAI API key set (${#OPENAI_API_KEY} chars)"
else
    echo "OPENAI_API_KEY not set - skipping API key injection"
fi

device_shell "appops set $PACKAGE SYSTEM_ALERT_WINDOW allow"
device_shell "pm grant $PACKAGE android.permission.RECORD_AUDIO"
device_shell "pm grant $PACKAGE android.permission.POST_NOTIFICATIONS"

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
