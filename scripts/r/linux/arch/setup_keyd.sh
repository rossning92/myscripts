# Key mapping using https://github.com/rvaiya/keyd
# Map "CapsLock" to "Control + Meta" key.

yay -S --noconfirm --needed --needed keyd

REAL_USER=${SUDO_USER:-$USER}
REAL_HOME=$(eval echo ~$REAL_USER)

sudo tee /etc/keyd/default.conf <<EOF
[ids]
*
[main]
rightcontrol = rightcontrol
capslock = overload(capslock, esc)

[capslock:C-M]
space = command(sudo -u $REAL_USER DISPLAY=:0 XAUTHORITY=$REAL_HOME/.Xauthority $REAL_HOME/myscripts/bin/run_script r/toggle_vncviewer.linux.sh)
EOF

sudo systemctl restart keyd.service --now
