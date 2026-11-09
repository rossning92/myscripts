# Autostart on any Linux desktop
mkdir -p ~/.config/autostart/
cat >~/.config/autostart/myscripts.desktop <<EOF
[Desktop Entry]
Type=Application
Name=myscripts
Exec=alacritty --title "myscriptsmgr" -o window.dynamic_title=false -e $HOME/myscripts/myscripts -t
StartupNotify=false
Terminal=false
EOF
