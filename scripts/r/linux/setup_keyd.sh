# Configure keyd on Arch Linux and Debian-based systems.
# Map CapsLock to a Control + Meta layer.
set -e

if [[ -f /etc/arch-release ]]; then
    yay -S --noconfirm --needed keyd
elif [[ -f /etc/debian_version ]]; then
    sudo apt-get install -y keyd
else
    echo 'Unsupported distribution: expected Arch or Debian-based Linux.' >&2
    exit 1
fi

real_user=${SUDO_USER:-$USER}
real_home=$(getent passwd "$real_user" | cut -d: -f6)
if [[ -z $real_home ]]; then
    echo "Unable to determine the home directory for $real_user." >&2
    exit 1
fi

sudo mkdir -p /etc/keyd
sudo tee /etc/keyd/default.conf >/dev/null <<EOF
[ids]
*
[main]
rightcontrol = rightcontrol
capslock = layer(capslock)

[capslock:C-M]
space = command(sudo -u $real_user DISPLAY=:0 XAUTHORITY=$real_home/.Xauthority $real_home/myscripts/bin/run_script r/toggle_vncviewer.linux.sh)
EOF

sudo systemctl enable keyd.service
sudo systemctl restart keyd.service
