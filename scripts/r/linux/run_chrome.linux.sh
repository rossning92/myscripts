if [[ -x "$(command -v chromium)" ]]; then
    policy_source="$(dirname "${BASH_SOURCE[0]}")/run_chrome.extensions-policy.json"
    policy_target="/etc/chromium/policies/managed/keepassxc-browser.json"

    if ! cmp -s "$policy_source" "$policy_target"; then
        echo "Installing Chromium extension policy..."
        sudo install -D -o root -g root -m 0644 "$policy_source" "$policy_target"
    fi

    nohup chromium --force-dark-mode >/dev/null 2>&1 &
fi
