#!/bin/bash

# class_name=.realvnc-vncviewer
class_name=org.remmina.Remmina

# Find all window IDs for the configured window class.
mapfile -t window_ids < <(wmctrl -lx | awk -v class_name="$class_name" \
    '$0 ~ class_name {print $1}')

if ((${#window_ids[@]})); then
    active_window_id=$(xprop -root _NET_ACTIVE_WINDOW | awk '{print $5}')
    for ((i = 0; i < ${#window_ids[@]}; i++)); do
        if ((active_window_id == window_ids[i])); then
            if ((i + 1 < ${#window_ids[@]})); then
                wmctrl -i -a "${window_ids[i + 1]}"
                exit
            fi

            # The last window is active, so minimize every Remmina window.
            for window_id in "${window_ids[@]}"; do
                wmctrl -i -r "$window_id" -b add,hidden
            done
            exit
        fi
    done

    # No Remmina window is active, so start the cycle at the first one.
    wmctrl -i -a "${window_ids[0]}"
else
    if [[ "$class_name" == "org.remmina.Remmina" ]]; then
        run_script r/vncviewer_remmina.sh
    else
        run_script r/vncviewer_realvnc.sh
    fi
fi
