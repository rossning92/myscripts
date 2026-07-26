#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

APK="app/build/outputs/apk/debug/app-debug.apk"

./gradlew assembleDebug
echo "APK built: $APK"
