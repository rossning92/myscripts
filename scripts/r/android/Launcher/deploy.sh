#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR/../../../../../Projects/launcher"

source "$SCRIPT_DIR/../android_helper.sh"

APK="$PROJECT_DIR/app/build/outputs/apk/debug/app-debug.apk"
PACKAGE="com.ross.launcher"

if [[ ! -d "$PROJECT_DIR/.git" ]]; then
    mkdir -p "$(dirname "$PROJECT_DIR")"
    gh repo clone rossning92/launcher "$PROJECT_DIR"
fi

run_script "$SCRIPT_DIR/build.sh"

android_install_apk "$APK"
android_shell "cmd package set-home-activity $PACKAGE/.MainActivity"
android_shell "am start -n $PACKAGE/.MainActivity"
