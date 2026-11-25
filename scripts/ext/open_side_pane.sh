#!/bin/bash
# Usage: open_side_pane.sh <command...>
# Runs <command...> in an unfocused right pane next to the caller's pane and prints the new pane id.
caller=$(run_script ext/get_caller_pane.sh)
tmux split-window -h -d -t "$caller" -P -F '#{pane_id}' "$@"
tmux select-layout -E -t "$caller"
