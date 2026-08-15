#!/usr/bin/env bash
set -euo pipefail

BUILD_FILE=${1:?Usage: build_and_install_gradle.sh BUILD_FILE}
PROJECT_DIR=$(cd -- "$(dirname -- "$BUILD_FILE")" && pwd)

run_script r/android/run_gradle.sh "$BUILD_FILE" assembleDebug

APK=$(
    find "$PROJECT_DIR" -path '*/build/outputs/apk/debug/*.apk' \
        ! -name '*androidTest*' ! -name '*unsigned*' -type f \
        -printf '%T@ %p\n' \
        | sort -nr \
        | head -n 1 \
        | cut -d' ' -f2-
)
if [[ -z "$APK" ]]; then
    echo "No debug APK was produced." >&2
    exit 1
fi

OUTPUT_METADATA=$(dirname -- "$APK")/output-metadata.json
if [[ ! -f "$OUTPUT_METADATA" ]]; then
    echo "Gradle output metadata not found: $OUTPUT_METADATA" >&2
    exit 1
fi

PACKAGE=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["applicationId"])' "$OUTPUT_METADATA")
run_script r/android/install_apk_rish.sh "$APK" "$PACKAGE"
