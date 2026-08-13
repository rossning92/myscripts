#!/bin/bash
set -euo pipefail

ndk_version="29.0.14206865"
install_dir="/usr/lib/android-sdk/ndk/$ndk_version"
clang="$install_dir/toolchains/llvm/prebuilt/linux-x86_64/bin/clang"

configure_gradle() {
    mkdir -p "$HOME/.gradle/init.d"
    sed "s/@NDK_VERSION@/$ndk_version/g" \
        "$(dirname "$0")/android_arm64_host.init.gradle" \
        > "$HOME/.gradle/init.d/myscripts-arm64-host.gradle"

    touch "$HOME/.gradle/gradle.properties"
    properties_tmp="$(mktemp "$HOME/.gradle/gradle.properties.XXXXXX")"
    sed '/^android\.aapt2FromMavenOverride=/d' \
        "$HOME/.gradle/gradle.properties" \
        > "$properties_tmp"
    echo "android.aapt2FromMavenOverride=/usr/lib/android-sdk/build-tools/debian/aapt2" \
        >> "$properties_tmp"
    mv "$properties_tmp" "$HOME/.gradle/gradle.properties"
}

is_arm64_clang() {
    [[ -x "$1" ]] && \
        "$1" --version | grep -q 'Target: aarch64-unknown-linux-musl'
}

if is_arm64_clang "$clang"; then
    configure_gradle
    echo "ARM64 Android NDK $ndk_version is ready: $install_dir"
    exit 0
fi

if [[ -e "$install_dir" ]]; then
    echo "Incomplete or invalid ARM64 NDK installation: $install_dir" >&2
    exit 1
fi

for tool in curl sha256sum tar; do
    if ! command -v "$tool" >/dev/null; then
        echo "$tool is required to install the ARM64 Android NDK" >&2
        exit 1
    fi
done

mkdir -p "$(dirname "$install_dir")"
setup_dir="$(mktemp -d "$(dirname "$install_dir")/.arm64-ndk.XXXXXX")"
trap 'find "$setup_dir" -depth -delete 2>/dev/null || true' EXIT
archive="$setup_dir/android-ndk.tar.xz"

curl -fL --retry 3 -o "$archive" \
    "https://github.com/lzhiyong/termux-ndk/releases/download/android-ndk/android-ndk-r29-aarch64.tar.xz"
printf '%s  %s\n' \
    "02e10e4ddfe8deaeb0bd0cf29d04c981ed5bc8a5d6b560ebb9e7661f472d684b" \
    "$archive" | sha256sum -c -
tar -xJf "$archive" -C "$setup_dir"

extracted_dir="$setup_dir/android-ndk-r29"
extracted_clang="$extracted_dir/toolchains/llvm/prebuilt/linux-x86_64/bin/clang"
if ! is_arm64_clang "$extracted_clang"; then
    echo "Installed NDK does not contain the expected ARM64-hosted compiler" >&2
    exit 1
fi

mv "$extracted_dir" "$install_dir"
configure_gradle
echo "Installed ARM64 Android NDK $ndk_version: $install_dir"
