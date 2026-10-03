#!/usr/bin/env bash
set -euo pipefail

# Override these when needed, for example:
# API_LEVEL=35 BUILD_TOOLS_VERSION=35.0.0 run_script r/android/install_android_sdk.linux.sh
api_level="${API_LEVEL:-36}"
build_tools_version="${BUILD_TOOLS_VERSION:-36.0.0}"
sdk_root="${ANDROID_HOME:-$HOME/Android/Sdk}"
tools_archive="commandlinetools-linux-15859902_latest.zip"
tools_sha256="4e4c464f145a7512b57d088ac6c278c03c9eea610886b35a5e0804e74eedf583"
tools_url="https://dl.google.com/android/repository/$tools_archive"

if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "x86_64" ]]; then
    echo "This installer supports Linux x86_64 only." >&2
    exit 1
fi

missing_packages=()
command -v curl >/dev/null 2>&1 || missing_packages+=(curl)
command -v unzip >/dev/null 2>&1 || missing_packages+=(unzip)
command -v java >/dev/null 2>&1 || missing_packages+=(default-jdk)

if ((${#missing_packages[@]})); then
    if ! command -v apt-get >/dev/null 2>&1; then
        echo "Missing: ${missing_packages[*]}. Install them with your system package manager." >&2
        exit 1
    fi

    sudo apt-get update
    sudo apt-get install -y "${missing_packages[@]}"
fi

mkdir -p "$sdk_root/cmdline-tools"

if [[ ! -x "$sdk_root/cmdline-tools/latest/bin/sdkmanager" ]]; then
    temp_dir="$(mktemp -d)"
    trap 'rm -rf -- "$temp_dir"' EXIT

    curl --fail --location --output "$temp_dir/$tools_archive" "$tools_url"
    printf '%s  %s\n' "$tools_sha256" "$temp_dir/$tools_archive" | sha256sum --check
    unzip -q "$temp_dir/$tools_archive" -d "$temp_dir/unpacked"
    mv "$temp_dir/unpacked/cmdline-tools" "$sdk_root/cmdline-tools/latest"
fi

export ANDROID_HOME="$sdk_root"
export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"

profile_file="$HOME/.bashrc"
profile_marker="# Android SDK (managed by install_android_sdk.linux.sh)"
if ! grep -Fq "$profile_marker" "$profile_file" 2>/dev/null; then
    {
        printf '\n%s\n' "$profile_marker"
        printf 'export ANDROID_HOME="%s"\n' "$sdk_root"
        printf 'export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"\n'
    } >>"$profile_file"
fi

sdkmanager --sdk_root="$ANDROID_HOME" \
    "platform-tools" \
    "platforms;android-$api_level" \
    "build-tools;$build_tools_version"

echo "Accept the Android SDK licenses:"
sdkmanager --sdk_root="$ANDROID_HOME" --licenses < <(yes)

echo
echo "Android SDK installed at $ANDROID_HOME"
echo "Installed Android API $api_level and Build Tools $build_tools_version"
echo "Run 'source $profile_file' to update this shell."
