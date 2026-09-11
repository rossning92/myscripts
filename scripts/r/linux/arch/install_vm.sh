set -euo pipefail

sudo pacman -S --needed --noconfirm \
    libvirt \
    virt-manager \
    qemu-full \
    edk2-ovmf \
    dnsmasq

sudo systemctl enable --now libvirtd.service

# Enable management of virtual machines without root
target_user="$USER"
sudo usermod -aG libvirt "$target_user"

# Enable automatic start of the default virtual network
sudo virsh net-autostart default
if ! sudo virsh net-list --name | grep -Fxq default; then
    sudo virsh net-start default
fi

if [[ ! -e /dev/kvm ]]; then
    echo "Warning: /dev/kvm is unavailable. Enable CPU virtualization in UEFI/BIOS." >&2
fi

echo "Virt-Manager setup complete."
echo "Log out and back in so the libvirt group membership takes effect for $target_user."
