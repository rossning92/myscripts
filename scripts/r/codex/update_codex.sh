#!/usr/bin/env bash
set -euo pipefail

codex_npm_prefix="$HOME/.npm-global"
exec "$codex_npm_prefix/bin/codex" update "$@"
