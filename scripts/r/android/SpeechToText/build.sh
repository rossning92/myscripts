#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

APK="app/build/outputs/apk/debug/app-debug.apk"

GRADLE_ARGS=()
# Google's Maven AAPT2 for Linux is x86-64, so use Debian's native binary on ARM64.
case "$(uname -m)" in
    aarch64|arm64)
        NATIVE_AAPT2="${ANDROID_HOME:-/usr/lib/android-sdk}/build-tools/debian/aapt2"
        if [[ ! -x "$NATIVE_AAPT2" ]]; then
            echo "ARM64 AAPT2 not found or not executable: $NATIVE_AAPT2" >&2
            exit 1
        fi
        GRADLE_ARGS+=("-Pandroid.aapt2FromMavenOverride=$NATIVE_AAPT2")
        ;;
esac

./gradlew "${GRADLE_ARGS[@]}" assembleDebug
echo "APK built: $APK"
