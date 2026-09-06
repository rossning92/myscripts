set -e

# Install and configure the NVIDIA open kernel driver.
# https://wiki.archlinux.org/title/NVIDIA#Xorg_configuration
if lspci -k | grep -q "NVIDIA Corporation"; then
    sudo pacman -S --noconfirm --needed nvidia-open nvidia-utils nvidia-settings
    sudo mkdir -p /etc/X11/xorg.conf.d
    sudo nvidia-xconfig \
        --metamodes="nvidia-auto-select +0+0 {ForceCompositionPipeline=On, ForceFullCompositionPipeline=On}" \
        --output-xconfig /etc/X11/xorg.conf.d/20-nvidia.conf
fi
