set -e

if [[ -z "$VNC_SERVER" ]]; then
	echo 'ERROR: Must specify VNC_SERVER'
	exit 1
fi

# Right Control+C to disconnect.
if [[ -f "$HOME/.config/remmina/remmina.pref" ]]; then
	sed -i 's/shortcutkey_disconnect=[0-9][0-9]*/shortcutkey_disconnect=99/g' "$HOME/.config/remmina/remmina.pref"
	sed -i 's/always_show_tab=true/always_show_tab=false/g' "$HOME/.config/remmina/remmina.pref"
	sed -i 's/hide_connection_toolbar=false/hide_connection_toolbar=true/g' "$HOME/.config/remmina/remmina.pref"
fi

mkdir -p "$HOME/.local/share/remmina"
profile_path="$HOME/.local/share/remmina/$VNC_SERVER.remmina"
if [[ ! -f "$profile_path" ]]; then
	cat >"$profile_path" <<EOF
[remmina]
name=$VNC_SERVER
server=$VNC_SERVER
protocol=VNC
scale=1
keyboard_grab=1
quality=1
colordepth=16
EOF
fi

# Known issues:
# 1. Shift+Tab hotkey does not work on remote desktop.
# 2. Mouse shortcut is grabbed.
nohup remmina "$profile_path" 2>/dev/null >/dev/null &
