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
echo "Pulling: $ROOT_DIR"
(cd "$ROOT_DIR" && "$GIT" pull --rebase) || true
