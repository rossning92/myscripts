set -e

# Install required packages
if [[ -f "/etc/debian_version" ]]; then
    packages="awesome xbacklight alsa-utils"
    for package in $packages; do
        dpkg -s "$package" >/dev/null 2>&1 || {
            sudo apt-get update
            sudo apt-get install -y "$package"
        }
    done
elif [[ -f "/etc/arch-release" ]]; then
    sudo pacman -S --noconfirm --needed awesome xorg-server xorg-xinit
fi

# Copy awesome config file
ln -sf "{{MYSCRIPT_ROOT}}/settings/awesome" $HOME/.config/

append_if_not_exist() {
    if [[ ! -f $1 ]] || ! grep -qF -- "$2" $1; then
        echo "$2" >>$1
    fi
}
# Replace the current process with AwesomeWM when initializing X.
append_if_not_exist "$HOME/.xinitrc" "exec awesome"
