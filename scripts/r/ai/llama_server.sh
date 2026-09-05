#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"

exec llama-server \
    --models-preset "$script_dir/llama_server.models.ini" \
    --models-max 1 \
    --host 127.0.0.1 \
    --port 8080
