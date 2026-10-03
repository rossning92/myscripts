#!/bin/bash
set -e
cd "$(dirname "$0")"

# Config ControlMaster on the client side to share SSH connections (multiplexing)
# mkdir -p ~/.ssh/
# printf "Host *\nControlMaster auto\nControlPath ~/.ssh/master-%%r@%%h:%%p.socket\n" >~/.ssh/config

# -t: interactive
ssh_command=""
if [[ -n "${_WSL}" ]]; then
    ssh_command+="cmd.exe /c "
fi
ssh_command+="ssh -t ${SSH_USER}@${SSH_HOST}"
ssh_command+=" -o \"StrictHostKeyChecking no\""
ssh_command+=" -o \"UseRoaming yes\""
ssh_command+=" -o \"ServerAliveInterval 60\""
if [ -n "${SSH_PORT}" ]; then
    ssh_command+=" -p ${SSH_PORT}"
fi
if [ -n "${SSH_LOCAL_PORT_FORWARD}" ]; then
    ssh_command+=" -L ${SSH_LOCAL_PORT_FORWARD}:localhost:${SSH_LOCAL_PORT_FORWARD}"
fi
if [[ -n "${_ADB_FORWARD}" ]]; then
    ssh_command+=" -R 15037:127.0.0.1:5037"
fi
if [[ -n "${_EXTRA_ARGS}" ]]; then
    ssh_command+=" ${_EXTRA_ARGS}"
fi
if [ -n "${_EXEC_COMMANDS}" ]; then
    ssh_command+=" ${_EXEC_COMMANDS}"
fi

if [[ -n "${_RUN_IN_SCREEN}" ]]; then
    ./screen/run_command_in_screen.sh ssh "${ssh_command}"
else
    eval "${ssh_command}"
fi
