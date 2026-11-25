#!/bin/bash
# Shows markdown from stdin in an unfocused right pane, replacing this window's previous one.
export TMUX_PANE=$(run_script ext/get_caller_pane.sh)
win=$(tmux display -p -t "$TMUX_PANE" '#{window_id}')
f=/tmp/show-markdown-pane-${win#@}.md
cat >"$f"
tmux list-panes -t "$win" -F '#{pane_id} #{pane_start_command}' | grep -F "$f" | cut -d' ' -f1 | xargs -r -n1 tmux kill-pane -t
run_script ext/open_side_pane.sh run_script ext/view_markdown.py "$f" >/dev/null
