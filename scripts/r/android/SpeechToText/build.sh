#!/bin/bash
set -e
cd "$(dirname "$0")"
./gradlew assembleDebug

if [[ "$1" == "--build-only" ]]; then
    echo "APK built: app/build/outputs/apk/debug/app-debug.apk"
    exit 0
fi

adb install -r --user 0 app/build/outputs/apk/debug/app-debug.apk
adb shell appops set com.ross.speechtotext SYSTEM_ALERT_WINDOW allow
adb shell pm grant com.ross.speechtotext android.permission.RECORD_AUDIO
adb shell pm grant com.ross.speechtotext android.permission.POST_NOTIFICATIONS

# Enable accessibility service (for auto-typing)
ENABLED=$(adb shell settings get secure enabled_accessibility_services)
SVC="com.ross.speechtotext/.TypeAccessibilityService"
if [[ "$ENABLED" != *"$SVC"* ]]; then
    if [ -z "$ENABLED" ] || [ "$ENABLED" = "null" ]; then
        adb shell settings put secure enabled_accessibility_services "$SVC"
    else
        adb shell settings put secure enabled_accessibility_services "$ENABLED:$SVC"
    fi
fi
adb shell settings put secure accessibility_enabled 1

adb shell am start -n com.ross.speechtotext/.MainActivity
