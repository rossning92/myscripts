#!/usr/bin/env bash
set -euo pipefail

BUILD_FILE=${1:?Usage: run_gradle.sh BUILD_FILE [GRADLE_ARGS...]}
shift

PROJECT_DIR=$(cd -- "$(dirname -- "$BUILD_FILE")" && pwd)
cd "$PROJECT_DIR"

if [[ -x ./gradlew ]]; then
    GRADLE=./gradlew
else
    GRADLE=gradle
fi

if [[ $# -eq 0 ]]; then
    set -- assembleDebug
fi

echo "+ $GRADLE $*"
"$GRADLE" "$@"
