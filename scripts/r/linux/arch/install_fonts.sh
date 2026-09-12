set -e

sudo pacman -S --noconfirm --needed \
    ttf-jetbrains-mono \
    $(pacman -Ssq 'noto-fonts-*')
