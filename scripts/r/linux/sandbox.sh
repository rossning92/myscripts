#!/usr/bin/env bash
# Usage: bash sandbox.sh command [args...]
# Keep the workspace narrow and exclude this launcher: secrets within it are
# exposed, and modified code can execute on the host after the sandbox exits.
# Networking stays shared by request, so localhost services and abstract Unix
# sockets remain reachable. This is filesystem isolation, not a VM boundary.
# HOME keeps its host path but starts empty, except for the mounted workspace.
# Personal credentials remain hidden, so agent logins are not preserved.
# Community: https://news.ycombinator.com/item?id=46626836
set -euo pipefail

die() { printf 'sandbox: %s\n' "$*" >&2; exit 2; }
(($#)) || die 'usage: bash sandbox.sh command [args...]'
[[ $(uname -s) == Linux ]] || die 'Linux is required'
((EUID != 0)) || die 'run as a regular user, without sudo'
command -v bwrap >/dev/null || die 'install bubblewrap first'
[[ $HOME == /* ]] || die 'HOME must be an absolute path'

workspace=$(realpath -e -- "${CWD:-$PWD}")
[[ -d $workspace ]] || die "not a directory: $workspace"
[[ $workspace != "$(realpath -e -- "$HOME")" ]] || die 'choose a project, not your entire home'
case "$workspace" in
    /|/home|/root|/run|/var|/tmp|/proc|/dev|/sys|/etc|/usr|/bin|/sbin|/lib|/lib64|\
    /proc/*|/dev/*|/sys/*|/run/*|/var/run/*)
        die "refusing broad or reserved workspace: $workspace" ;;
esac

args=(
    --unshare-all --share-net --die-with-parent --new-session --cap-drop ALL
    --clearenv --proc /proc --dev /dev --tmpfs /tmp --dir /run
    --dir /var --symlink /run /var/run --symlink /tmp /var/tmp
    --dir /home --dir "$HOME" --dir /etc
)
for path in /usr /bin /sbin /lib /lib64; do
    [[ -e $path ]] && args+=(--ro-bind "$path" "$path")
done
# Expose user-installed npm tools and their packages, without home credentials.
for path in "$HOME/.npm-global/bin" "$HOME/.npm-global/lib/node_modules"; do
    [[ -d $path ]] && args+=(--ro-bind "$path" "$path")
done
# Avoid mounting all of /etc, which can contain service credentials.
for path in /etc/alternatives /etc/ssl/certs /etc/pki/tls/certs \
    /etc/ld.so.cache /etc/ld.so.conf /etc/ld.so.conf.d \
    /etc/nsswitch.conf /etc/hosts /etc/resolv.conf /etc/gai.conf \
    /etc/localtime /etc/mime.types; do
    [[ -e $path ]] && args+=(--ro-bind "$path" "$path")
done
# Tools need UID lookups; synthetic records avoid exposing host account details.
args+=(
    --ro-bind-data 3 /etc/passwd --ro-bind-data 4 /etc/group
    --bind "$workspace" "$workspace"
    --chdir "$workspace"
    --setenv HOME "$HOME" --setenv USER sandbox --setenv LOGNAME sandbox
    --setenv PATH "$HOME/.npm-global/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    --setenv TMPDIR /tmp
    --setenv LANG "${LANG:-C.UTF-8}" --setenv TERM "${TERM:-xterm-256color}"
)
# Don't pass inherited agent sockets or other open files through the sandbox.
for entry in /proc/$$/fd/*; do
    fd=${entry##*/}
    if [[ $fd =~ ^[0-9]+$ ]] && ((fd > 2 && fd != 255)); then
        exec {fd}>&-
    fi
done
gid=$(id -g)
exec bwrap "${args[@]}" -- "$@" \
    3<<<"sandbox:x:$UID:$gid:Sandbox:$HOME:/bin/bash" \
    4<<<"sandbox:x:$gid:"
