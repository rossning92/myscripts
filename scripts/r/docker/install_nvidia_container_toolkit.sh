#!/usr/bin/env bash
set -euo pipefail

if dpkg -s nvidia-container-toolkit >/dev/null 2>&1; then
    exit 0
fi

# Reuse an existing NVIDIA repository when it already provides the toolkit.
if ! apt-cache show nvidia-container-toolkit >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y --no-install-recommends ca-certificates curl gnupg
    repo_dir="$(mktemp -d)"
    trap 'rm -rf -- "$repo_dir"' EXIT
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
        -o "$repo_dir/key.asc"
    gpg --batch --dearmor --output "$repo_dir/key.gpg" "$repo_dir/key.asc"
    sudo install -m 644 "$repo_dir/key.gpg" \
        /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
        -o "$repo_dir/toolkit.list"
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
        "$repo_dir/toolkit.list" > "$repo_dir/signed.list"
    sudo install -m 644 "$repo_dir/signed.list" \
        /etc/apt/sources.list.d/nvidia-container-toolkit.list
    sudo apt-get update
fi

sudo apt-get install -y nvidia-container-toolkit
