#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$HOME/Projects/launcher"

source "$SCRIPT_DIR/../android_helper.sh"

APK="$PROJECT_DIR/app/build/outputs/apk/debug/app-debug.apk"
PACKAGE="com.ross.launcher"

run_script "$SCRIPT_DIR/build.sh"

android_install_apk "$APK"
android_shell "cmd package set-home-activity $PACKAGE/.MainActivity"
android_shell "am start -n $PACKAGE/.MainActivity"
