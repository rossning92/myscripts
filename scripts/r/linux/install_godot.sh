#!/usr/bin/env bash
set -euo pipefail

case "$(uname -m)" in
    x86_64) arch=x86_64 ;;
    aarch64 | arm64) arch=arm64 ;;
    armv7l) arch=arm32 ;;
    i686) arch=x86_32 ;;
    *) echo "Unsupported architecture: $(uname -m)" >&2; exit 1 ;;
esac

url=$(curl -fsSL https://api.github.com/repos/godotengine/godot-builds/releases/latest |
    sed -nE "s/.*\"browser_download_url\": \"([^\"]+_linux\.${arch}\.zip)\".*/\1/p")
if [[ -z "$url" ]]; then
    echo "No Godot download found for $arch." >&2
    exit 1
fi

download_dir=$(mktemp -d)
trap 'rm -rf "$download_dir"' EXIT
curl -fL "$url" -o "$download_dir/godot.zip"
unzip -q "$download_dir/godot.zip" -d "$download_dir"
mkdir -p "$HOME/.local/bin"
install -m 755 "$download_dir/$(basename "$url" .zip)" "$HOME/.local/bin/godot"
echo "Installed: $HOME/.local/bin/godot"
