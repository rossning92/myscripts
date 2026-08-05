#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR/../../../../../Projects/launcher"

cd "$PROJECT_DIR"

./gradlew assembleDebug
echo "APK built: app/build/outputs/apk/debug/app-debug.apk"
