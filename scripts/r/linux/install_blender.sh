#!/usr/bin/env bash
set -euo pipefail

# Install Blender 5.3.0 for Linux x64.
[[ "$(uname -sm)" == 'Linux x86_64' ]] || { echo 'Requires Linux x64.' >&2; exit 1; }

version=5.3.0
# https://mirror.blender.org/release/Blender5.3/blender-5.3.0.sha256
sha256=dacb8264197a3f7fda6001285a5a506fc97ee943881261c2c3bd63c882f22e05

install_dir="$HOME/software/blender"
bin_link="$HOME/.local/bin/blender"
if [[ -e "$bin_link" && ! -L "$bin_link" ]]; then
    echo "Refusing to replace existing file: $bin_link" >&2
    exit 1
fi

download_dir=$(mktemp -d)
trap 'rm -rf -- "$download_dir"' EXIT
curl -fL "https://mirror.blender.org/release/Blender${version%.*}/blender-${version}-linux-x64.tar.xz" \
    -o "$download_dir/blender.tar.xz"
printf '%s  %s\n' "$sha256" "$download_dir/blender.tar.xz" | sha256sum --check -
mkdir -p "$install_dir" "$HOME/.local/bin"
tar -xJf "$download_dir/blender.tar.xz" -C "$install_dir" --strip-components=1
"$install_dir/blender" --version
ln -sfnT "$install_dir/blender" "$bin_link"
echo "Installed: $install_dir"
