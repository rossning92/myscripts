#!/bin/bash
set -e

# Get the root directory of the current script repo
ROOT_DIR="$(realpath "$(dirname "$0")/../../")"

sync_repo() (
    cd "$1" || exit 1
    if [[ ! -d ".git" ]]; then
        echo "Skipping non-git directory: $(pwd)"
        return 0
    fi
    if [[ -n "$AMEND" ]]; then
        echo "Sync repo (amend): $(pwd)"
    else
        echo "Sync repo: $(pwd)"
    fi

    # Check if file is modified
    status=$(git status --short)
    if [[ ! -z "$status" ]]; then
        GIT_REPO="$(cygpath -w "$(pwd)" 2>/dev/null || pwd)" run_script.exe r/git/git_diff.py
        echo "Confirm? (y/n)"
        read -n1 ans </dev/tty
        echo
        if [[ "$ans" == "y" ]]; then
            git add -A

            if [[ -n "$AMEND" ]]; then
                git commit --amend --no-edit
            else
                git commit -m 'No commit message'
            fi
        else
            return 0
        fi
    fi

    echo 'Sync changes with remote...'
    if [[ -n "$AMEND" ]]; then
        git push --force
    else
        git pull --rebase

        git push
    fi
)

# Sync current script directory
sync_repo "$ROOT_DIR"

# Update submodules
if [ -d "$ROOT_DIR/scripts/r/videoedit/movy" ]; then
    if (cd "$ROOT_DIR/scripts/r/videoedit/movy" && git diff --quiet); then
        echo "Update submodule movy..."
        (cd "$ROOT_DIR" && git submodule update --recursive --remote || true)
    else
        echo "(Skip updating submodule movy - working tree is dirty.)"
    fi
fi

# Sync additional script directories
for line in $(run_script ext/get_script_dirs.py); do
    line="${line%$'\r'}"
    if [[ -z "$line" ]]; then
        continue
    fi

    if [[ -d "$line" ]]; then
        # Skip if it is the same as the main script directory
        if [[ "$(realpath "$line")" != "$(realpath "$ROOT_DIR")" ]]; then
            sync_repo "$line"
        fi
    fi
done
