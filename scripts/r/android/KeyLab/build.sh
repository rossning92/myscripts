#!/bin/bash
set -e
cd "$(dirname "$0")"

# AGP needs JDK 11+; the default `java` on the devserver is 8. Prefer a full JDK 17.
JDK17=/usr/local/fbprojects/packages/java-runtime/prod/impl/17
if [ -x "$JDK17/bin/javac" ]; then export JAVA_HOME="$JDK17"; fi

./gradlew assembleDebug

if [[ "$1" == "--build-only" ]]; then
    echo "APK built: app/build/outputs/apk/debug/app-debug.apk"
    exit 0
fi

adb install -r --user 0 app/build/outputs/apk/debug/app-debug.apk

# Enable the accessibility service (intercepts hardware keys).
SVC="com.ross.keylab/.LongPressAccessibilityService"
ENABLED=$(adb shell settings get secure enabled_accessibility_services)
if [[ "$ENABLED" != *"$SVC"* ]]; then
    if [ -z "$ENABLED" ] || [ "$ENABLED" = "null" ]; then
        adb shell settings put secure enabled_accessibility_services "$SVC"
    else
        adb shell settings put secure enabled_accessibility_services "$ENABLED:$SVC"
    fi
fi
adb shell settings put secure accessibility_enabled 1

adb shell am start -n com.ross.keylab/.MainActivity
