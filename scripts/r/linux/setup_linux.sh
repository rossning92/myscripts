# Shared desktop setup for Arch Linux and Debian-based systems.
set -e

if [[ -f /etc/arch-release ]]; then
    distro=arch
elif [[ -f /etc/debian_version ]]; then
    distro=debian
else
    echo 'Unsupported distribution: expected Arch or Debian-based Linux.' >&2
    exit 1
fi

append_line_dedup() {
    touch "$1"
    if ! grep -qFx -- "$2" "$1"; then
        printf '%s\n' "$2" >>"$1"
    fi
}

gpu_info=''
if command -v lspci >/dev/null 2>&1; then
    gpu_info=$(lspci -k)
else
    echo 'Skipping GPU configuration: lspci is not installed (install pciutils).' >&2
fi
has_nvidia_gpu=false
has_intel_gpu=false
if [[ $gpu_info == *'NVIDIA Corporation'* ]]; then
    has_nvidia_gpu=true
fi
if [[ $gpu_info == *'Intel Corporation UHD Graphics 615'* || $gpu_info == *'Intel Corporation UHD Graphics 630'* ]]; then
    has_intel_gpu=true
fi
has_unifying_receiver=false
if grep -ql 'Unifying Receiver' /sys/bus/usb/devices/*/product 2>/dev/null; then
    has_unifying_receiver=true
fi
has_backlight=false
if [[ -d /sys/class/backlight ]]; then
    has_backlight=true
fi

common_packages=(acpi alacritty curl fzf git less neovim playerctl unzip usbutils wmctrl xclip zip
    bluez pulseaudio pavucontrol alsa-utils udisks2 udiskie
    fcitx5 fcitx5-chinese-addons pqiv awesome sxhkd zathura flameshot i3lock xss-lock)

if [[ $distro == arch ]]; then
    packages=("${common_packages[@]}" inetutils openssh
        ttf-jetbrains-mono base-devel
        bluez-utils bluez-tools pulseaudio-bluetooth network-manager-applet earlyoom
        fcitx5-qt fcitx5-gtk fcitx5-configtool
        xorg-server xorg-xinit parcellite zathura-pdf-mupdf)
    mapfile -t noto_fonts < <(pacman -Ssq 'noto-fonts-*')
    packages+=("${noto_fonts[@]}")
    if [[ $has_nvidia_gpu == true ]]; then
        packages+=(nvidia-open nvidia-utils nvidia-settings)
    fi
    if [[ $has_intel_gpu == true ]]; then
        packages+=(xf86-video-intel)
    fi
else
    packages=("${common_packages[@]}" inetutils-tools openssh-client
        fonts-jetbrains-mono fonts-noto-core fonts-noto-cjk
        blueman pulseaudio-module-bluetooth network-manager-gnome
        fcitx5-frontend-qt5 fcitx5-frontend-gtk3 fcitx5-config-qt
        xorg xinit clipit zathura-pdf-poppler)
    if [[ $has_intel_gpu == true ]]; then
        packages+=(xserver-xorg-video-intel)
    fi
fi
if [[ $has_unifying_receiver == true ]]; then
    packages+=(solaar)
fi
if [[ $has_backlight == true ]]; then
    packages+=(brightnessctl)
fi

if [[ $distro == arch ]]; then
    sudo pacman -S --noconfirm --needed "${packages[@]}"
    run_script r/linux/arch/install_yay.sh
    sudo systemctl enable --now systemd-resolved.service earlyoom.service
    run_script r/linux/arch/setup_keyd.sh
else
    # TODO: Install the Debian NVIDIA driver and firmware when an NVIDIA GPU is detected.
    # This requires contrib, non-free, and non-free-firmware APT components.
    sudo apt-get install -y "${packages[@]}"
    # TODO: Decide whether Debian needs equivalents for the Arch-only
    # systemd-resolved, earlyoom, and keyd setup.
fi

if [[ $has_nvidia_gpu == true ]]; then
    if command -v nvidia-xconfig >/dev/null 2>&1; then
        sudo mkdir -p /etc/X11/xorg.conf.d
        sudo nvidia-xconfig \
            --metamodes="nvidia-auto-select +0+0 {ForceCompositionPipeline=On, ForceFullCompositionPipeline=On}" \
            --output-xconfig /etc/X11/xorg.conf.d/20-nvidia.conf
    else
        echo 'Skipping NVIDIA Xorg configuration: nvidia-xconfig is not installed.' >&2
    fi
fi
if [[ $has_intel_gpu == true ]]; then
    sudo mkdir -p /etc/X11/xorg.conf.d
    if [[ $gpu_info == *'Intel Corporation UHD Graphics 630'* ]]; then
        triple_buffer='  Option "TripleBuffer" "true"'
    else
        triple_buffer=''
    fi
    sudo tee /etc/X11/xorg.conf.d/20-intel.conf >/dev/null <<EOF
Section "Device"
  Identifier "Intel Graphics"
  Driver "intel"
  Option "TearFree" "true"
${triple_buffer}
EndSection
EOF
fi

# Make JetBrains Mono the preferred monospace face on both distributions.
mkdir -p "$HOME/.config/fontconfig/conf.d"
cat >"$HOME/.config/fontconfig/conf.d/50-monospace.conf" <<'FONTCONFIG'
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig>
  <alias>
    <family>monospace</family>
    <prefer><family>JetBrains Mono</family></prefer>
  </alias>
</fontconfig>
FONTCONFIG
fc-cache -f

sudo timedatectl set-ntp true
if timezone=$(curl -fsS --max-time 10 https://ipapi.co/timezone); then
    if timedatectl list-timezones | grep -qFx -- "$timezone"; then
        sudo timedatectl set-timezone "$timezone"
    else
        echo "Skipping timezone setup: invalid timezone from ipapi.co: $timezone" >&2
    fi
else
    echo 'Skipping timezone setup: ipapi.co is unavailable; keeping the current timezone.' >&2
fi

append_line_dedup "$HOME/.xinitrc" 'nm-applet &'
sudo systemctl enable --now bluetooth.service
append_line_dedup "$HOME/.xinitrc" 'udiskie &'

sudo sed -i -E 's/^#?HandlePowerKey=.*/HandlePowerKey=suspend/' /etc/systemd/logind.conf
sudo systemctl kill -s HUP systemd-logind

touch "$HOME/.xprofile"
for im_var in 'XMODIFIERS=@im=fcitx' 'QT_IM_MODULE=fcitx' 'GTK_IM_MODULE=fcitx'; do
    line="export $im_var"
    sed -i "\|^${line}$|d" "$HOME/.xprofile"
    sed -i "1i $line" "$HOME/.xprofile"
done
if ! pgrep -x fcitx5 >/dev/null; then
    fcitx5 -d &>/dev/null
    sleep 2
fi
gdbus call --session --dest org.fcitx.Fcitx5 --object-path /controller \
    --method org.fcitx.Fcitx.Controller1.SetInputMethodGroupInfo \
    "Default" "us" "[('keyboard-us', ''), ('pinyin', '')]"
gdbus call --session --dest org.fcitx.Fcitx5 --object-path /controller \
    --method org.fcitx.Fcitx.Controller1.Save
mkdir -p "$HOME/.config/fcitx5"
cat >"$HOME/.config/fcitx5/config" <<'FCITX'
[Hotkey/TriggerKeys]
0=Super+space

[Hotkey/EnumerateGroupForwardKeys]
0=Super+space

[Hotkey/EnumerateGroupBackwardKeys]
0=Shift+Super+space
FCITX
fcitx5-remote -r &>/dev/null || true

if [[ ${has_unifying_receiver:-false} == true ]]; then
    append_line_dedup "$HOME/.xinitrc" 'solaar --window hide &'
fi
if [[ $distro == arch ]]; then
    append_line_dedup "$HOME/.xinitrc" 'parcellite &'
else
    append_line_dedup "$HOME/.xinitrc" 'clipit &'
fi

sudo mkdir -p /etc/X11/xorg.conf.d
sudo tee /etc/X11/xorg.conf.d/70-synaptics.conf >/dev/null <<'XORG'
Section "InputClass"
    Identifier "touchpad"
    Option "tapping" "on"
    Option "VertScrollDelta" "-111"
    Option "HorizScrollDelta" "-111"
EndSection
XORG

append_line_dedup "$HOME/.xinitrc" 'alacritty -e "$HOME/myscripts/myscripts" --startup &'

# Keep sudoers syntax validated before installing it.
sudoers_line="$(whoami) ALL=(ALL:ALL) NOPASSWD: ALL"
if ! sudo grep -qFx -- "$sudoers_line" /etc/sudoers; then
    printf '%s\n' "$sudoers_line" | sudo tee /etc/sudoers.d/myscripts >/dev/null
    sudo chmod 0440 /etc/sudoers.d/myscripts
    sudo visudo -cf /etc/sudoers.d/myscripts
fi

config_dir="${XDG_CONFIG_HOME:-${HOME}/.config}"
mkdir -p "$config_dir"
ln -sfn "{{MYSCRIPT_ROOT}}/settings/pqiv/pqivrc" "$config_dir/pqivrc"
while IFS= read -r mime_type; do
    [[ $mime_type == image/* ]] && xdg-mime default pqiv.desktop "$mime_type"
done < <(sed -n 's/^MimeType=//p' /usr/share/applications/pqiv.desktop | tr ';' '\n')
xdg-mime default org.pwmt.zathura.desktop application/pdf

append_line_dedup "$HOME/.xinitrc" 'flameshot &'
append_line_dedup "$HOME/.xinitrc" 'xss-lock --transfer-sleep-lock -- i3lock --nofork -c 000000 &'
mkdir -p "$HOME/.config"
ln -sf "{{MYSCRIPT_ROOT}}/settings/awesome" "$HOME/.config/"
dpi_value=120
if [[ -f /sys/class/dmi/id/product_name ]] && grep -q 'Surface Go 3' /sys/class/dmi/id/product_name; then
    dpi_value=144
fi
touch "$HOME/.Xresources"
if grep -q '^Xft\.dpi:' "$HOME/.Xresources"; then
    sed -i "s/^Xft\.dpi:.*/Xft.dpi: $dpi_value/" "$HOME/.Xresources"
else
    echo "Xft.dpi: $dpi_value" >>"$HOME/.Xresources"
fi
startx_line='[[ -z $DISPLAY ]] && [[ $(tty) = /dev/tty1 ]] && startx'
append_line_dedup "$HOME/.bash_profile" "$startx_line"
touch "$HOME/.xinitrc"
sed -i '\|^xrdb -merge ~/.Xresources$|d; \|^exec awesome$|d' "$HOME/.xinitrc"
sed -i '1i xrdb -merge ~/.Xresources' "$HOME/.xinitrc"
echo 'exec awesome' >>"$HOME/.xinitrc"

# XXX: Disable the old suspend service, if present, so it does not race with xss-lock.
sudo systemctl disable "betterlockscreen@$(whoami).service" 2>/dev/null || true
