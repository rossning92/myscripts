set -e

file_append() {
    if [[ ! -f $1 ]] || ! grep -qF -- "$2" $1; then
        echo "$2" >>$1
    fi
}

export DEFAULT_ALWAYS_YES=true
export ASSUME_ALWAYS_YES=true

# Update packages and force use of new configuration files
pkg up -y -o Dpkg::Options::="--force-confnew"

# ==============================
# Install packages
# ==============================
declare -a packages=(
    "sed"
    "termux-api"
)
for package in "${packages[@]}"; do
    dpkg -s "$package" >/dev/null 2>&1 || {
        pkg update
        pkg install -y "$package"
    }
done

# Workaround for major performance degradation with most termux-api calls
# See https://github.com/termux/termux-api/issues/552
# sed -i 's#^exec /system/bin/app_process /#exec /system/bin/app_process -Xnoimage-dex2oat /#' "$PREFIX/bin/am"

# Config termux
if [ -d "$HOME/.termux" ] && [ ! -L "$HOME/.termux" ]; then
    rm -rf "$HOME/.termux"
fi
ln -sfn "$HOME/myscripts/settings/termux" "$HOME/.termux"
termux-reload-settings

# Set up hooks for sharing to Termux
mkdir -p "$HOME/bin"
termux_context_menu="$HOME/myscripts/settings/termux/termux-file-editor"
chmod 700 "$termux_context_menu"
ln -sfn "$termux_context_menu" "$HOME/bin/termux-file-editor"
ln -sfn "$termux_context_menu" "$HOME/bin/termux-url-opener"
