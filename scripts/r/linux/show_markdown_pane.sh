#!/bin/bash
# Shows markdown from stdin in an unfocused right pane, replacing this window's previous one.
# Finds the caller's pane from its process tree when TMUX_PANE is unset, so the pane doesn't land in the focused window.
if [[ -z "$TMUX_PANE" ]]; then
    p=$$
    while [[ "$p" -gt 1 && -z "$TMUX_PANE" ]]; do
        TMUX_PANE=$(tmux list-panes -a -F '#{pane_pid} #{pane_id}' | awk -v p="$p" '$1 == p {print $2}')
        p=$(ps -o ppid= -p "$p" | tr -d ' ')
    done
fi
win=$(tmux display -p -t "$TMUX_PANE" '#{window_id}')
f=/tmp/show-markdown-pane-${win#@}.md
cat >"$f"
tmux list-panes -t "$win" -F '#{pane_id} #{pane_start_command}' | grep -F "$f" | cut -d' ' -f1 | xargs -r -n1 tmux kill-pane -t
pane=$(tmux split-window -h -d -P -F '#{pane_id}' -t "$TMUX_PANE" "~/.venv/myscripts/bin/python -m rich.markdown -c -t monokai -w \$(tput cols) $f | less -R")
# Re-render at the new width when the pane is resized. Drop the hook once the pane is gone, however it was closed.
tmux set-hook -w -t "$win" 'window-layout-changed[99]' "run-shell 'tmux respawn-pane -k -t $pane || tmux set-hook -uw -t $win window-layout-changed[99]'"
tmux select-layout -E -t "$TMUX_PANE"
