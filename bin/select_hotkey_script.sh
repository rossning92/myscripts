#!/usr/bin/env bash

# Select which script to run when multiple scripts share a global hotkey.
set -u

if (( $# < 2 )); then
    exit 1
fi

python_executable=$1
shift
script_dir=$(cd -- "$(dirname -- "$0")" && pwd)
rofi_config="$script_dir/../settings/rofi/config.rasi"

rofi_dpi=""
if [[ -r "$HOME/.Xresources" ]]; then
    while IFS=: read -r resource value; do
        if [[ $resource == "Xft.dpi" ]]; then
            rofi_dpi=${value//[[:space:]]/}
            break
        fi
    done < "$HOME/.Xresources"
fi

rofi_args=(
    -config "$rofi_config"
    -theme-str "#listview { lines: $#; }"
    -dmenu
    -i
    -no-custom
    -p "select script"
)
for number in {1..9}; do
    rofi_args+=("-kb-custom-$number" "$number")
done
rofi_args+=(-kb-custom-10 "0")

if [[ $rofi_dpi =~ ^[0-9]+([.][0-9]+)?$ ]]; then
    rofi_args+=(-dpi "$rofi_dpi")
fi

menu_items=""
index=1
for script_path in "$@"; do
    menu_items+="${index}  ${script_path##*/}"$'\n'
    ((index++))
done

selection=$(
    printf '%s' "$menu_items" | rofi "${rofi_args[@]}"
)
rofi_status=$?

if (( rofi_status >= 10 && rofi_status <= 19 )); then
    selected_index=$((rofi_status - 9))
elif (( rofi_status == 0 )); then
    selected_index=${selection%% *}
else
    exit 0
fi

if [[ ! $selected_index =~ ^[0-9]+$ ]] || (( selected_index < 1 || selected_index > $# )); then
    exit 0
fi

selected_script=${!selected_index}
exec "$python_executable" "$script_dir/start_script.py" \
    --restart-instance=auto "$selected_script"
