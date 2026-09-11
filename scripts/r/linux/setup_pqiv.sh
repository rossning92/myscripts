#!/usr/bin/env bash

set -euo pipefail

if [[ ! -f /etc/arch-release ]]; then
    echo "This setup script currently supports Arch Linux only." >&2
    exit 1
fi

if ! command -v pqiv >/dev/null 2>&1; then
    sudo pacman -S --needed --noconfirm pqiv
fi

config_dir="${XDG_CONFIG_HOME:-${HOME}/.config}"
desktop_id="pqiv.desktop"
desktop_path="/usr/share/applications/${desktop_id}"
settings_dir="{{MYSCRIPT_ROOT}}/settings/pqiv"

mkdir -p "$config_dir"

ln -sfn "${settings_dir}/pqivrc" "${config_dir}/pqivrc"

# pqiv also advertises support for PDFs, videos, and archives. Only make it the
# default for images so this setup does not replace unrelated MIME handlers.
while IFS= read -r mime_type; do
    [[ $mime_type == image/* ]] && xdg-mime default "$desktop_id" "$mime_type"
done < <(sed -n 's/^MimeType=//p' "$desktop_path" | tr ';' '\n')

echo "pqiv is installed and configured to browse sibling images."
