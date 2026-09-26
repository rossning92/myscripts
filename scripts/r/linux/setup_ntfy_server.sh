#!/usr/bin/env bash
set -euo pipefail

ip=${1:-10.77.0.1}
port=${2:-2586}
dir=${XDG_CONFIG_HOME:-$HOME/.config}/ntfy-server

mkdir -p "$dir"
cat >"$dir/compose.yml" <<EOF
services:
  ntfy:
    image: binwiederhier/ntfy:latest
    container_name: ntfy
    command:
      - serve
      - --base-url=http://$ip:$port
      - --cache-file=/var/cache/ntfy/cache.db
      - --attachment-cache-dir=/var/cache/ntfy/attachments
    ports:
      - "$ip:$port:80"
    volumes:
      - cache:/var/cache/ntfy
    restart: unless-stopped

volumes:
  cache:
EOF

if docker compose version >/dev/null 2>&1; then
    compose=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
    compose=(docker-compose)
else
    echo "Docker Compose is required but is not installed." >&2
    exit 1
fi

"${compose[@]}" -f "$dir/compose.yml" up -d
echo "ntfy is available at http://$ip:$port"
