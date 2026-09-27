set -euo pipefail

if command -v pacman >/dev/null; then
    sudo pacman -S --needed --noconfirm \
        libvirt \
        virt-manager \
        qemu-full \
        edk2-ovmf \
        dnsmasq
elif command -v apt-get >/dev/null; then
    sudo apt-get update
    sudo apt-get install --yes \
        qemu-system-x86 \
        libvirt-daemon-system \
        virt-manager \
        ovmf \
        swtpm-tools
else
    echo "Error: neither pacman nor apt-get is available." >&2
    exit 1
fi

sudo systemctl enable --now libvirtd.service

# Enable management of virtual machines without root
target_user="$USER"
sudo usermod -aG libvirt "$target_user"
if getent group kvm >/dev/null; then
    sudo usermod -aG kvm "$target_user"
fi

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
