#!/usr/bin/env bash
set -euo pipefail

device=${1:-}

if [[ -z $device ]]; then
    root=$(findmnt -no SOURCE / | cut -d '[' -f1)
    root=$(readlink -f "$root")
    device=$(lsblk -srnpo PATH,FSTYPE "$root" | awk '$2 == "crypto_LUKS" { print $1; exit }')
fi

[[ -b $device ]] || { echo "Usage: $0 [/dev/LUKS_PARTITION]" >&2; exit 1; }
[[ $(sudo cryptsetup luksDump "$device" | awk '/^Version:/ {print $2}') == 2 ]] || {
    echo "LUKS2 required: $device" >&2
    exit 1
}
mokutil --sb-state | grep -q 'SecureBoot enabled' || {
    echo "Enable Secure Boot first." >&2
    exit 1
}
[[ -e /dev/tpmrm0 ]] || { echo "TPM2 not detected." >&2; exit 1; }

sudo apt-get update
sudo apt-get install -y tpm2-tools clevis-tpm2 clevis-luks clevis-initramfs

slot=$(sudo clevis luks list -d "$device" 2>/dev/null |
    awk '$2 == "tpm2" && !slot { sub(":", "", $1); slot = $1 } END { print slot }')

if [[ -z $slot ]]; then
    echo "Enter the existing LUKS password. Its key slot will be preserved."
    sudo clevis luks bind -d "$device" tpm2 \
        '{"hash":"sha256","key":"ecc","pcr_bank":"sha256","pcr_ids":"7"}'
    slot=$(sudo clevis luks list -d "$device" |
        awk '$2 == "tpm2" && !slot { sub(":", "", $1); slot = $1 } END { print slot }')
fi

set +o pipefail
sudo clevis luks pass -d "$device" -s "$slot" |
    sudo cryptsetup open --test-passphrase --key-file=- "$device"
test_status=${PIPESTATUS[1]}
set -o pipefail
((test_status == 0)) || exit "$test_status"
sudo update-initramfs -u -k all

echo "TPM auto-unlock ready on $device (Clevis slot $slot)."
echo "Reboot to test; use the existing LUKS password if TPM unlock fails."
