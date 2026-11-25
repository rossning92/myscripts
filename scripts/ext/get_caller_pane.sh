#!/bin/bash
# Prints the tmux pane id of the calling process.
# Finds it from the process tree when TMUX_PANE is unset, so callers don't fall back to the focused window.
if [[ -z "$TMUX_PANE" ]]; then
    p=$$
    while [[ "$p" -gt 1 && -z "$TMUX_PANE" ]]; do
        TMUX_PANE=$(tmux list-panes -a -F '#{pane_pid} #{pane_id}' | awk -v p="$p" '$1 == p {print $2}')
        p=$(ps -o ppid= -p "$p" | tr -d ' ')
    done
fi
echo "$TMUX_PANE"
