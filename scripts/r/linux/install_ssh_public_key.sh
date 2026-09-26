#!/usr/bin/env sh

set -eu

key=${SSH_KEY:-$HOME/.ssh/id_ed25519.pub}

if [ ! -f "$key" ]; then
    mkdir -p "$HOME/.ssh"
    chmod 700 "$HOME/.ssh"
    ssh-keygen -t ed25519 -f "${key%.pub}"
fi

exec ssh-copy-id -i "$key" -p "${SSH_PORT:-22}" "$SSH_USER@$SSH_HOST"
