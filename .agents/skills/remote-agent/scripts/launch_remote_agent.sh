#!/usr/bin/env bash
set -e

remote_command='start_script --run-in-tmux r/ai/agent.py'
if [[ -n "${1:-}" ]]; then
    printf -v prompt '%q' "$1"
    remote_command+=" --prompt $prompt"
fi

ssh -t -p 22 ross@10.77.0.1 "$remote_command"
tmux select-window -t remote_shell
