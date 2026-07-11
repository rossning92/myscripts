#!/bin/bash
set -e
cd "$(dirname "$0")"

export JAVA_HOME=$(ls -d /usr/lib/jvm/java-17-openjdk* | head -1)

./gradlew assembleDebug

if [[ "$1" == "--build-only" ]]; then
    echo "APK built: app/build/outputs/apk/debug/app-debug.apk"
    exit 0
fi

SERIAL=$(adb devices -l | awk '/product:mustang/ {print $1; exit}')
if [ -z "$SERIAL" ]; then
    echo "mustang not found in 'adb devices'"
    exit 1
fi

adb -s "$SERIAL" install -r app/build/outputs/apk/debug/app-debug.apk
adb -s "$SERIAL" shell cmd package set-home-activity com.ross.launcher/.MainActivity
adb -s "$SERIAL" shell am start -n com.ross.launcher/.MainActivity
