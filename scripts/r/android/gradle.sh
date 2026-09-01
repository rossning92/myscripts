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

printf '+ %q' "$GRADLE"
printf ' %q' "$@"
printf '\n'
"$GRADLE" "$@"
