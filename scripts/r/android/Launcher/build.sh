#!/bin/bash
set -e

PROJECT_DIR="$HOME/Projects/launcher"

if [[ ! -d "$PROJECT_DIR/.git" ]]; then
    mkdir -p "$HOME/Projects"
    gh repo clone rossning92/launcher "$PROJECT_DIR"
fi

cd "$PROJECT_DIR"

./gradlew assembleDebug
echo "APK built: app/build/outputs/apk/debug/app-debug.apk"
