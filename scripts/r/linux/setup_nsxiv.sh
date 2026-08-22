#!/usr/bin/env bash

set -euo pipefail

if [[ ! -f /etc/arch-release ]]; then
    echo "This setup script currently supports Arch Linux only." >&2
    exit 1
fi

if ! command -v nsxiv >/dev/null 2>&1; then
    sudo pacman -S --needed nsxiv
fi

wrapper_dir="${HOME}/.local/bin"
applications_dir="${HOME}/.local/share/applications"
nsxiv_exec_dir="${XDG_CONFIG_HOME:-${HOME}/.config}/nsxiv/exec"
wrapper_path="${wrapper_dir}/nsxiv-folder"
desktop_id="nsxiv-folder.desktop"
desktop_path="${applications_dir}/${desktop_id}"
image_info_path="${nsxiv_exec_dir}/image-info"
settings_dir="{{MYSCRIPT_ROOT}}/settings/nsxiv"

mkdir -p "$wrapper_dir" "$applications_dir" "$nsxiv_exec_dir"

path_export='export PATH="$HOME/.local/bin:$PATH"'
touch "${HOME}/.xinitrc"
if ! grep -qFx -- "$path_export" "${HOME}/.xinitrc"; then
    sed -i "1i${path_export}" "${HOME}/.xinitrc"
fi

ln -sfn "${settings_dir}/nsxiv-folder" "$wrapper_path"
ln -sfn "${settings_dir}/exec/image-info" "$image_info_path"
ln -sfn "${settings_dir}/nsxiv-folder.desktop" "$desktop_path"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$applications_dir"
fi

# Register every MIME type declared by the desktop entry, keeping it as the single source of truth.
while IFS= read -r mime_type; do
    [[ -n $mime_type ]] && xdg-mime default "$desktop_id" "$mime_type"
done < <(sed -n 's/^MimeType=//p' "$desktop_path" | tr ';' '\n')

echo "nsxiv is installed and configured to browse sibling images."
