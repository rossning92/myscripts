#!/usr/bin/env bash
set -euo pipefail

if [ ! -f /etc/debian_version ]; then
    if ! command -v proot-distro >/dev/null 2>&1; then
        echo "proot-distro is not installed. Run: pkg install proot-distro" >&2
        exit 127
    fi

    if ! proot-distro list 2>&1 | grep -q "^  \* debian$"; then
        echo "Debian is not installed. Run: proot-distro install debian" >&2
        exit 1
    fi

    exec proot-distro login debian -- bash "$0" "$@"
fi

printf 'inside_proot_debian=true\n'
printf 'debian_version=%s\n' "$(cat /etc/debian_version)"
printf 'user=%s\n' "$(whoami)"
printf 'pwd=%s\n' "$PWD"
printf 'uname=%s\n' "$(uname -a)"
printf 'args=%s\n' "$*"
printf 'command_output=%s\n' "$(bash -lc 'echo hello from Debian PRoot')"
