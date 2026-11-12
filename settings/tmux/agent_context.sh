#!/bin/bash
pane_pid=$(tmux display -p '#{pane_pid}')
cmdline=$(ps -o args= -p "$(ps -o tpgid= -p "$pane_pid")")
tmux display -p "<terminal_context source=\"tmux\" scope=\"current-pane\" window=\"#{window_index}:#{window_name}\" cmdline=\"$cmdline\" cwd=\"#{pane_current_path}\" includes=\"visible-screen\">"
tmux capture-pane -p
printf '\n</terminal_context>'
