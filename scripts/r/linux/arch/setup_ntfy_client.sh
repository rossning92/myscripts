#!/usr/bin/env bash
set -euo pipefail

url=${1:?"Usage: $0 https://ntfy.sh/TOPIC"}
host=${url%/*}
topic=${url##*/}
[[ $host =~ ^https?://[^/]+$ && $topic =~ ^[A-Za-z0-9_-]+$ ]] || {
    echo "Invalid ntfy topic URL: $url" >&2
    exit 2
}

case $(uname -m) in
    x86_64) arch=amd64 ;;
    aarch64) arch=arm64 ;;
    armv7l) arch=armv7 ;;
    *) echo "Unsupported architecture: $(uname -m)" >&2; exit 1 ;;
esac

command -v notify-send >/dev/null || sudo pacman -S --needed libnotify

releases=https://github.com/binwiederhier/ntfy/releases
release=$(curl -fsSL -o /dev/null -w '%{url_effective}' "$releases/latest")
version=${release##*/v}
tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
archive="ntfy_${version}_linux_${arch}"

curl -fL "$releases/download/v$version/${archive}.tar.gz" -o "$tmp/ntfy.tar.gz"
tar -xzf "$tmp/ntfy.tar.gz" -C "$tmp"
install -Dm755 "$tmp/$archive/ntfy" "$HOME/.local/bin/ntfy"

mkdir -p "$HOME/.config/ntfy" "$HOME/.config/systemd/user"
cat >"$HOME/.config/ntfy/client.yml" <<EOF
default-host: $host
subscribe:
  - topic: $topic
    command: 'notify-send "\${NTFY_TITLE:-ntfy}" "\$NTFY_MESSAGE"'
EOF

cat >"$HOME/.config/systemd/user/ntfy-client.service" <<'EOF'
[Unit]
Description=ntfy desktop notifications
After=network-online.target
[Service]
ExecStart=%h/.local/bin/ntfy subscribe --config %h/.config/ntfy/client.yml --from-config
Restart=on-failure
[Install]
WantedBy=default.target
EOF

systemctl --user enable --now ntfy-client
systemctl --user restart ntfy-client

echo "Listening for $url"
