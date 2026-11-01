#!/usr/bin/env bash
set -euo pipefail

if [[ -x ./gradlew ]]; then
    GRADLE=./gradlew
else
    GRADLE=gradle
fi

if [[ $# -eq 0 ]]; then
    set -- assembleDebug
fi

if [[ ${1:-} == --accept-licenses ]]; then
    android_home="${ANDROID_HOME:-$HOME/Android/Sdk}"
    sdkmanager="$android_home/cmdline-tools/latest/bin/sdkmanager"
    if [[ ! -x $sdkmanager ]]; then
        sdkmanager="$(command -v sdkmanager || true)"
    fi
    if [[ -z $sdkmanager ]]; then
        echo "sdkmanager not found." >&2
        exit 1
    fi
    printf '+ %q --sdk_root=%q --licenses\n' "$sdkmanager" "$android_home"
    yes | "$sdkmanager" --sdk_root="$android_home" --licenses
    exit
fi

printf '+ %q' "$GRADLE"
printf ' %q' "$@"
printf '\n'
"$GRADLE" "$@"
