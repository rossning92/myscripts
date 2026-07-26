#!/bin/bash
set -e
cd "$(dirname "$0")"

export JAVA_HOME=$(ls -d /usr/lib/jvm/java-17-openjdk* | head -1)

./gradlew assembleDebug
echo "APK built: app/build/outputs/apk/debug/app-debug.apk"
