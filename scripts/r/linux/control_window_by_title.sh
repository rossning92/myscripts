#!/bin/bash

app=$1
match_mode=${2:-4}
command=${3:-activate}

matched_win_ids=$(
    wmctrl -l | while read -r win_id _desktop _host title; do
        case "$match_mode" in
            0) [[ "$title" == "$app" ]] ;;
            1) [[ "$title" == *"$app"* ]] ;;
            2) [[ "$title" == "$app"* ]] ;;
            3) [[ "$title" =~ $app ]] ;;
            4) [[ "$title" == "$app"* || "$title" == *"$app" ]] ;;
            5) [[ "$title" == *"$app" ]] ;;
            *) continue ;;
        esac
        [[ $? -eq 0 ]] && echo "$win_id"
    done
)
win_ids=($(xprop -root | awk -F'# ' '/_NET_CLIENT_LIST_STACKING/ {gsub(/,/, " "); print $2}'))

found=false
if [[ "$command" == "close" ]]; then
    for i in $matched_win_ids; do
        found=true
        wmctrl -i -c "$i"
    done
    [[ "$found" == true ]] && exit 0 || exit 1
fi

for ((idx = ${#win_ids[@]} - 1; idx >= 0; idx--)); do
    for i in $matched_win_ids; do
        if ((i == win_ids[idx])); then
            found=true
            if ((idx < ${#win_ids[@]} - 1)); then
                wmctrl -ia $i
                exit 0
            fi
        fi
    done
done

[[ "$found" == true ]] && exit 0 || exit 1
