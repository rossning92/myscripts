#!/bin/bash
set -e
cd "$(dirname "$0")"
./gradlew assembleDebug

if [[ "$1" == "--build-only" ]]; then
    echo "APK built: app/build/outputs/apk/debug/app-debug.apk"
    exit 0
fi

adb install -r --user 0 app/build/outputs/apk/debug/app-debug.apk

# force-stop before enabling accessibility below: it clears the enabled service.
if [ -n "$OPENAI_API_KEY" ]; then
    PREFS="/data/data/com.ross.speechtotext/shared_prefs/com.ross.speechtotext_preferences.xml"
    adb shell am force-stop com.ross.speechtotext
    printf "<?xml version='1.0' encoding='utf-8' standalone='yes' ?>\n<map>\n    <string name=\"openai_api_key\">%s</string>\n</map>\n" "$OPENAI_API_KEY" |
        adb shell "run-as com.ross.speechtotext sh -c 'cat > $PREFS'"
    echo "OpenAI API key set (${#OPENAI_API_KEY} chars)"
else
    echo "OPENAI_API_KEY not set - skipping API key injection"
fi

adb shell appops set com.ross.speechtotext SYSTEM_ALERT_WINDOW allow
adb shell pm grant com.ross.speechtotext android.permission.RECORD_AUDIO
adb shell pm grant com.ross.speechtotext android.permission.POST_NOTIFICATIONS

# Enable accessibility service (for auto-typing)
ENABLED=$(adb shell settings get secure enabled_accessibility_services)
SVC="com.ross.speechtotext/com.ross.speechtotext.TypeAccessibilityService"
if [[ "$ENABLED" != *"$SVC"* ]]; then
    if [ -z "$ENABLED" ] || [ "$ENABLED" = "null" ]; then
        adb shell settings put secure enabled_accessibility_services "$SVC"
    else
        adb shell settings put secure enabled_accessibility_services "$ENABLED:$SVC"
    fi
fi
adb shell settings put secure accessibility_enabled 1

adb shell am start -n com.ross.speechtotext/.MainActivity
