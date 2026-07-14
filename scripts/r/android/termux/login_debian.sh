#!/usr/bin/env bash
set -e

export DEFAULT_ALWAYS_YES=true
export ASSUME_ALWAYS_YES=true

distro=debian

login() {
    proot-distro login "$distro"
}

install_proot_distro() {
    pkg update
    pkg install -y proot-distro
}

is_installed() {
    proot-distro list 2>/dev/null | grep -q "^  \* $distro$"
}

login && exit 0
status=$?

if [ "$status" -eq 127 ]; then
    install_proot_distro
    login && exit 0
    status=$?
fi

if is_installed; then
    exit "$status"
fi

proot-distro install "$distro"
exec proot-distro login "$distro"
