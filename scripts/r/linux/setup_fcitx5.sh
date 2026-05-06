# https://wiki.archlinux.org/title/Fcitx5

append_line_dedup() {
    touch "$1"
    # Remove the line if it exists and then append it
    if [[ -f "$1" ]] && grep -qF -- "$2" "$1"; then
        repl=$(printf '%s\n' "$2" | sed -e 's/[]\/$*.^[]/\\&/g')
        sed -i "\%^$repl$%d" "$1"
    fi
    echo "$2" >>"$1"
}

prepend_line_dedup() {
    # Remove the line if it exists and then prepend it
    if [[ -f "$1" ]] && grep -qF -- "$2" "$1"; then
        repl=$(printf '%s\n' "$2" | sed -e 's/[]\/$*.^[]/\\&/g')
        sed -i "\%^$repl$%d" "$1"
    fi
    printf '%s\n%s\n' "$2" "$(cat $1)" >"$1"
}

# Install fcitx5 and addons
sudo pacman -S --noconfirm --needed \
    fcitx5 \
    fcitx5-qt \
    fcitx5-gtk \
    fcitx5-configtool \
    fcitx5-chinese-addons

# Add environment variables for IM
prepend_line_dedup ~/.xinitrc "export XMODIFIERS=@im=fcitx"
prepend_line_dedup ~/.xinitrc "export QT_IM_MODULE=fcitx"
prepend_line_dedup ~/.xinitrc "export GTK_IM_MODULE=fcitx"
append_line_dedup ~/.xinitrc "fcitx5 -d"

# Start fcitx5 if not running
if ! pgrep -x fcitx5 >/dev/null; then
    fcitx5 -d &>/dev/null
    sleep 2 # wait for it to start
fi

# Programmatically add pinyin input method using gdbus
# This ensures pinyin is added to the "Default" group
gdbus call --session --dest org.fcitx.Fcitx5 --object-path /controller \
    --method org.fcitx.Fcitx.Controller1.SetInputMethodGroupInfo \
    "Default" "us" "[('keyboard-us', ''), ('pinyin', '')]"

# Save changes to the profile file
gdbus call --session --dest org.fcitx.Fcitx5 --object-path /controller \
    --method org.fcitx.Fcitx.Controller1.Save
