#!/usr/bin/env bash

set -euo pipefail

repo_dir="${1:-.}"

if [[ ! -d "$repo_dir" ]]; then
    echo "ERROR: Directory does not exist: $repo_dir" >&2
    exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
    echo "ERROR: GitHub CLI (gh) is not installed." >&2
    exit 1
fi

cd "$repo_dir"
repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || {
    echo "ERROR: '$repo_dir' is not inside a Git repository." >&2
    exit 1
}
cd "$repo_root"

if ! git rev-parse --verify HEAD >/dev/null 2>&1; then
    echo "ERROR: The Git repository does not have a commit to push." >&2
    exit 1
fi

if git remote get-url origin >/dev/null 2>&1; then
    echo "ERROR: Remote 'origin' already exists: $(git remote get-url origin)" >&2
    exit 1
fi

gh auth status >/dev/null
repo_name="$(basename "$repo_root")"
current_branch="$(git branch --show-current)"

if [[ -z "$current_branch" ]]; then
    echo "ERROR: Cannot push from a detached HEAD." >&2
    exit 1
fi

read -r -p "Create private GitHub repo '$repo_name' and push '$current_branch'? [y/N]: " confirm
if [[ "${confirm,,}" != "y" && "${confirm,,}" != "yes" ]]; then
    echo "Cancelled."
    exit 0
fi

gh repo create "$repo_name" --private --source=. --remote=origin --push

gh repo view --json nameWithOwner,visibility,url --jq '"Created and pushed: \(.nameWithOwner) [\(.visibility)]\n\(.url)"'
