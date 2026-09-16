#!/bin/bash

if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "mingw"* ]]; then
    GIT="/c/Program Files/Git/bin/git.exe"
    export GIT_CONFIG_COUNT=2
    export GIT_CONFIG_KEY_0=credential.helper
    export GIT_CONFIG_VALUE_0=
    export GIT_CONFIG_KEY_1=credential.helper
    export GIT_CONFIG_VALUE_1=manager
else
    GIT="git"
fi

ROOT_DIR="$(realpath "$(dirname "$0")/../../")"

pull_repo() {
    echo "Pulling: $1"
    (cd "$1" && "$GIT" pull --rebase) || true
}

pull_repo "$ROOT_DIR"

for dir in $(run_script ext/get_script_dirs.py); do
    dir="${dir%$'\r'}"
    if [[ -d "$dir/.git" && "$(realpath "$dir")" != "$ROOT_DIR" ]]; then
        pull_repo "$dir"
    fi
done
