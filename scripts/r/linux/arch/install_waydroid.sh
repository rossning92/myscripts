#!/usr/bin/env bash

set -euo pipefail

sudo pacman -S --needed --noconfirm waydroid cage git base-devel

if ! command -v yay >/dev/null; then
    run_script r/linux/arch/install_yay.sh
fi

# Build AUR Python packages against Arch's system Python, not the virtual
# environment activated by the myscripts launcher.
env -u VIRTUAL_ENV -u PYTHONHOME -u PYTHONPATH PATH=/usr/bin:/bin \
    yay -S --needed --noconfirm waydroid-script-git

if [[ ! -f /var/lib/waydroid/images/system.img ]]; then
    sudo waydroid init
fi

sudo systemctl enable --now waydroid-container.service
sudo waydroid-extras install libndk
sudo systemctl restart waydroid-container.service

echo "Waydroid with ARM support is installed."
