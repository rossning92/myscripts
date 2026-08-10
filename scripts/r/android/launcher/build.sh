#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
MYSCRIPTS_DIR=$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)
PROJECT_DIR=${LAUNCHER_DIR:-"$MYSCRIPTS_DIR/repos/launcher"}

"$SCRIPT_DIR/bootstrap.sh"

cd "$PROJECT_DIR"

./gradlew assembleDebug
echo "APK built: $PROJECT_DIR/app/build/outputs/apk/debug/app-debug.apk"
