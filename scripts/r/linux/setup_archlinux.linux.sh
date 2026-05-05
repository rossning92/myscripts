set -e

prepend_line_dedup() {
    # Remove the line if it exists and then prepend it
    if [[ -f "$1" ]] && grep -qF -- "$2" "$1"; then
        repl=$(printf '%s\n' "$2" | sed -e 's/[]\/$*.^[]/\\&/g')
        sed -i "\%^$repl$%d" "$1"
    fi
    printf '%s\n%s\n' "$2" "$(cat $1)" >"$1"
}

append_line_dedup() {
    touch "$1"
    # Remove the line if it exists and then append it
    if [[ -f "$1" ]] && grep -qF -- "$2" "$1"; then
        repl=$(printf '%s\n' "$2" | sed -e 's/[]\/$*.^[]/\\&/g')
        sed -i "\%^$repl$%d" "$1"
    fi
    echo "$2" >>"$1"
}

append_line_sudo() {
    if [[ ! -f $1 ]] || ! sudo grep -qF -- "$2" $1; then
        echo "$2" | sudo tee -a $1
    fi
}

pac_install() {
    sudo pacman -S --noconfirm --needed "$@"
}

yay_install() {
    yay -S --noconfirm --needed --needed "$@"
}

# Install utilities.
# - acpi: for battery monitor
pac_install \
    acpi \
    alacritty \
    fzf \
    git \
    inetutils \
    less \
    neovim \
    openssh \
    playerctl \
    sxhkd \
    unzip \
    usbutils \
    wmctrl \
    xclip \
    zip
append_line_dedup "$HOME/.bashrc" 'alias v=nvim'

# Install fonts
pac_install $(pacman -Ssq 'noto-fonts-*') ttf-noto-nerd
pac_install ttf-jetbrains-mono

{{ include('r/linux/arch/install_yay.sh') }}

# Configure HiDPI display
DPI_VALUE=120 # 96 * 1.25
if [[ -f /sys/class/dmi/id/product_name ]] && grep -q "Surface Go 3" /sys/class/dmi/id/product_name; then
    DPI_VALUE=144
fi
if ! grep -qF -- "Xft.dpi" ~/.Xresources; then
    echo "Xft.dpi: $DPI_VALUE" >>~/.Xresources
else
    sed -i "s/Xft.dpi:.*/Xft.dpi: $DPI_VALUE/" ~/.Xresources
fi
# This should be the first line of .xinitrc, so that all other apps can get the correct DPI value.
prepend_line_dedup ~/.xinitrc "xrdb -merge ~/.Xresources"

# Network manager
pac_install network-manager-applet
append_line_dedup ~/.xinitrc "nm-applet &"

# Bluetooth
# - bluez and bluez-utils: a Linux Bluetooth stack
# - blueman: GUI tool for desktop environments
pac_install bluez bluez-utils bluez-tools # blueman
# append_line_dedup ~/.xinitrc "blueman-applet &"
sudo systemctl enable bluetooth.service --now
# then you can use bluetoothctl to pair in command line

# Setup audio
pac_install pulseaudio pavucontrol pulseaudio-bluetooth
pac_install alsa-utils # for amixer CLI command

# Set power key to suspend
# https://wiki.archlinux.org/title/Power_management#ACPI_events
sudo sed -i -E 's/^#?HandlePowerKey=.*/HandlePowerKey=suspend/' /etc/systemd/logind.conf
sudo systemctl kill -s HUP systemd-logind

run_script r/linux/setup_fcitx5.sh
run_script r/linux/arch/setup_keyd.sh

# Automatically run startx without using display manager / login manager.
append_line_dedup \
    "$HOME/.bash_profile" \
    '[[ -z $DISPLAY ]] && [[ $(tty) = /dev/tty1 ]] && startx'

# Configure bash alias.
append_line_dedup "$HOME/.bashrc" 'alias v="nvim"'
append_line_dedup "$HOME/.bashrc" 'alias i="sudo pacman -S --noconfirm"'

# Automatically mount USB devices
pac_install udisks2 udiskie
append_line_dedup ~/.xinitrc "udiskie &"

# Install window manager
{{ include('r/linux/setup_awesomewm.sh') }}

# Enable DNS resolve caching.
sudo systemctl enable --now systemd-resolved.service

# To avoid freezing at low memory
pac_install earlyoom
sudo systemctl enable earlyoom --now

# ------------------------------
# Hardware specific (TODO: move)
# ------------------------------

# Install proprietary NVIDIA GPU driver.
# https://wiki.archlinux.org/title/NVIDIA#Xorg_configuration
if lspci -k | grep -q "NVIDIA Corporation"; then
    kernel_version=$(uname -r)
    if [[ $kernel_version == *lts* ]]; then
        pac_install nvidia-lts
    else
        pac_install nvidia-open
    fi
    pac_install nvidia-settings
    sudo nvidia-xconfig --metamodes="nvidia-auto-select +0+0 {ForceCompositionPipeline=On, ForceFullCompositionPipeline=On}" --output-xconfig /etc/X11/xorg.conf.d/20-nvidia.conf
fi

# Setup Intel graphics.
# https://wiki.archlinux.org/title/intel_graphics
if lspci -k | grep -q "Intel Corporation UHD Graphics 615"; then
    # Provides the legacy intel DDX driver from Gen 2 to Gen 9 hardware
    pac_install xf86-video-intel

    sudo mkdir -p /etc/X11/xorg.conf.d/
    sudo bash -c 'cat > /etc/X11/xorg.conf.d/20-intel.conf <<EOF
Section "Device"
  Identifier "Intel Graphics"
  Driver "intel"
  Option "TearFree" "true"
EndSection
EOF'
fi

if lspci -k | grep -q "Intel Corporation UHD Graphics 630"; then
    pac_install xf86-video-intel

    sudo mkdir -p /etc/X11/xorg.conf.d/
    sudo bash -c 'cat > /etc/X11/xorg.conf.d/20-intel.conf <<EOF
Section "Device"
  Identifier "Intel Graphics"
  Driver "intel"
  Option "TearFree" "true"
  Option "TripleBuffer" "true"
EndSection
EOF'
fi

# Setup keyboard
setup_logitech_keyboard() {
    if lsusb | grep -q "Unifying Receiver"; then
        pac_install solaar # Logitech device manager
        append_line_dedup ~/.xinitrc 'solaar --window hide &'
    fi
}
setup_logitech_keyboard

# Setup clipboard manager
setup_clipboard_manager() {
    pac_install parcellite
    append_line_dedup ~/.xinitrc 'parcellite &'
}
setup_clipboard_manager

# Backlight control
if [ -d /sys/class/backlight ]; then
    pac_install brightnessctl
fi

# Configure Touchpad:
# https://wiki.archlinux.org/title/Touchpad_Synaptics
sudo tee /etc/X11/xorg.conf.d/70-synaptics.conf <<EOF
Section "InputClass"
    Identifier "touchpad"
    Option "tapping" "on"
    # Natural scrolling:
    Option "VertScrollDelta" "-111"
    Option "HorizScrollDelta" "-111"
EndSection
EOF

# Auto-start MyScript
append_line_dedup ~/.xinitrc 'alacritty -e "$HOME/myscripts/myscripts" --startup &'

# Disable sudo password
append_line_sudo /etc/sudoers "$(whoami) ALL=(ALL:ALL) NOPASSWD: ALL"

# ------------
# Install Apps
# ------------

# Screenshot
pac_install flameshot
append_line_dedup ~/.xinitrc 'flameshot &'

run_script r/linux/arch/setup_lock_screen.sh

# Replace the current process with the awesomewm when initializing X.
append_line_dedup ~/.xinitrc "exec awesome"

run_script r/install_package.py vscode
run_script r/install_package.py google-chrome

# System time
sudo timedatectl set-ntp true
# Set the timezone based on geo-location:
timedatectl set-timezone $(curl -s https://ipapi.co/timezone)

# Install GitHub CLI
pac_install github-cli
if [[ "$(gh auth status 2>&1)" =~ "not logged" ]]; then
    gh auth login
fi
