#!/usr/bin/env bash
set -euo pipefail

source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
sdk=${ANDROID_HOME:-"$HOME/Android/Sdk"}
platform="$sdk/platforms/android-35/android.jar"
build_tools="$sdk/build-tools/36.0.0"
work_dir=$(mktemp -d "$source_dir/.build.XXXXXXXX")
trap 'rm -r -- "$work_dir"' EXIT

javac --release 11 -classpath "$platform" -d "$work_dir" "$source_dir/ReadClipboardUri.java"
"$build_tools/d8" --lib "$platform" --min-api 29 \
    --output "$work_dir/clipboard-uri.jar" "$work_dir/ReadClipboardUri.class"
mv -fT -- "$work_dir/clipboard-uri.jar" "$source_dir/clipboard-uri.jar"
