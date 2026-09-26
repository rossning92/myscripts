#!/usr/bin/env bash
set -euo pipefail

case "$(uname -m)" in
    x86_64)
        archive_arch=x86_64
        tree_sitter_arch=x64
        ;;
    aarch64 | arm64)
        archive_arch=arm64
        tree_sitter_arch=arm64
        ;;
    *)
        echo "Unsupported architecture: $(uname -m)" >&2
        exit 1
        ;;
esac

install_dir="/opt/nvim-linux-${archive_arch}"
archive="nvim-linux-${archive_arch}.tar.gz"
download_dir="$(mktemp -d)"
trap 'rm -rf "$download_dir"' EXIT

curl -fL "https://github.com/neovim/neovim/releases/latest/download/${archive}" \
    -o "${download_dir}/${archive}"
sudo mkdir -p /opt
sudo tar -C /opt -xzf "${download_dir}/${archive}"
sudo ln -sfn "${install_dir}/bin/nvim" /usr/local/bin/nvim

tree_sitter_archive="tree-sitter-cli-linux-${tree_sitter_arch}.zip"
curl -fL "https://github.com/tree-sitter/tree-sitter/releases/latest/download/${tree_sitter_archive}" \
    -o "${download_dir}/${tree_sitter_archive}"
unzip -q "${download_dir}/${tree_sitter_archive}" -d "${download_dir}/tree-sitter"
sudo install -m 0755 "${download_dir}/tree-sitter/tree-sitter" /usr/local/bin/tree-sitter

nvim --version | head -n 1
tree-sitter --version
