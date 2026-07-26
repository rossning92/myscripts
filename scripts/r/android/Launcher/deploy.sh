#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

source ../android_helper.sh

APK="app/build/outputs/apk/debug/app-debug.apk"
PACKAGE="com.ross.launcher"

run_script ./build.sh

android_install_apk "$APK"
android_shell "cmd package set-home-activity $PACKAGE/.MainActivity"
android_shell "am start -n $PACKAGE/.MainActivity"
