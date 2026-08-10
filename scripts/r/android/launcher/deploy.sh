#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
MYSCRIPTS_DIR=$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)
PROJECT_DIR=${LAUNCHER_DIR:-"$MYSCRIPTS_DIR/repos/launcher"}

source "$SCRIPT_DIR/../android_helper.sh"

APK="$PROJECT_DIR/app/build/outputs/apk/debug/app-debug.apk"
PACKAGE="com.ross.launcher"

run_script "$SCRIPT_DIR/build.sh"

android_install_apk "$APK"
android_shell "cmd package set-home-activity $PACKAGE/.MainActivity"
android_shell "am start -n $PACKAGE/.MainActivity"
