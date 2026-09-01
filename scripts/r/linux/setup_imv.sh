#!/usr/bin/env bash

set -euo pipefail

if [[ ! -f /etc/arch-release ]]; then
    echo "This setup script currently supports Arch Linux only." >&2
    exit 1
fi

if ! command -v imv >/dev/null 2>&1; then
    sudo pacman -S --needed imv
fi

config_dir="${XDG_CONFIG_HOME:-${HOME}/.config}/imv"
desktop_id="imv-dir.desktop"
desktop_path="/usr/share/applications/${desktop_id}"
settings_dir="{{MYSCRIPT_ROOT}}/settings/imv"

mkdir -p "$config_dir"

ln -sfn "${settings_dir}/config" "${config_dir}/config"

# Register every MIME type supported by imv's packaged directory-browsing entry.
while IFS= read -r mime_type; do
    [[ -n $mime_type ]] && xdg-mime default "$desktop_id" "$mime_type"
done < <(sed -n 's/^MimeType=//p' "$desktop_path" | tr ';' '\n')

echo "imv is installed and configured to browse sibling images."
