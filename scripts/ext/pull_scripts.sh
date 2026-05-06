#!/bin/bash

if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "mingw"* ]]; then
    GIT="/c/Program Files/Git/bin/git.exe"
else
    GIT="git"
fi

ROOT_DIR="$(realpath "$(dirname "$0")/../../")"
echo "Pulling: $ROOT_DIR"
(cd "$ROOT_DIR" && "$GIT" pull --rebase) || true

while IFS= read -r dir; do
    dir="${dir%$'\r'}"
    if [[ -d "$dir" && -d "$dir/.git" ]]; then
        echo "Pulling: $dir"
        (cd "$dir" && "$GIT" pull --rebase) || true
    fi
done < <(run_script ext/get_script_dirs.py)
