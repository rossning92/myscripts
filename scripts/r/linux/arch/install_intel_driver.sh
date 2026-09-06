set -e

pac_install() {
    sudo pacman -S --noconfirm --needed "$@"
}

gpu_info=$(lspci -k)

# Configure the legacy Intel DDX driver for the machines that need it.
# https://wiki.archlinux.org/title/intel_graphics
if grep -q "Intel Corporation UHD Graphics 615" <<<"$gpu_info"; then
    pac_install xf86-video-intel
    sudo mkdir -p /etc/X11/xorg.conf.d
    sudo tee /etc/X11/xorg.conf.d/20-intel.conf >/dev/null <<'EOF'
Section "Device"
  Identifier "Intel Graphics"
  Driver "intel"
  Option "TearFree" "true"
EndSection
EOF
elif grep -q "Intel Corporation UHD Graphics 630" <<<"$gpu_info"; then
    pac_install xf86-video-intel
    sudo mkdir -p /etc/X11/xorg.conf.d
    sudo tee /etc/X11/xorg.conf.d/20-intel.conf >/dev/null <<'EOF'
Section "Device"
  Identifier "Intel Graphics"
  Driver "intel"
  Option "TearFree" "true"
  Option "TripleBuffer" "true"
EndSection
EOF
fi
