# https://wiki.archlinux.org/title/CUPS

set -e
sudo pacman -S --noconfirm cups ghostscript
sudo systemctl enable cups.service --now
lpadmin -p Brother_HL-L2460DW -E -v "ipp://BRW4C82A9805513.local/ipp" -m everywhere
