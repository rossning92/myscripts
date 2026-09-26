if [[ -x "$(command -v chromium)" ]]; then
    nohup chromium --force-dark-mode --user-data-dir="$HOME/.config/chromium-2" >/dev/null 2>&1 &
fi
