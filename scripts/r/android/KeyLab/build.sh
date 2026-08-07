#!/bin/bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$SCRIPT_DIR"

PREFERRED_JAVA_HOME=${PREFERRED_JAVA_HOME:-/usr/local/fbprojects/packages/java-runtime/prod/impl/17}
GRADLE_BUILD_TASK=${GRADLE_BUILD_TASK:-assembleDebug}
APK_PATH=${APK_PATH:-app/build/outputs/apk/debug/app-debug.apk}

if [[ -x "$PREFERRED_JAVA_HOME/bin/javac" ]]; then
    export JAVA_HOME="$PREFERRED_JAVA_HOME"
fi

./gradlew "$GRADLE_BUILD_TASK"
echo "APK built: $APK_PATH"
