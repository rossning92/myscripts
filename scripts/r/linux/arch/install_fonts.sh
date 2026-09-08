set -e

sudo pacman -S --noconfirm --needed \
    ttf-jetbrains-mono \
    $(pacman -Ssq 'noto-fonts-*')

# Make JetBrains Mono the default for applications that request the generic
# monospace family.
mkdir -p "$HOME/.config/fontconfig/conf.d"
cat >"$HOME/.config/fontconfig/conf.d/50-monospace.conf" <<'EOF'
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig>
  <alias>
    <family>monospace</family>
    <prefer>
      <family>JetBrains Mono</family>
    </prefer>
  </alias>
</fontconfig>
EOF
fc-cache -f
