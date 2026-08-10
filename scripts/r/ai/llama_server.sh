#!/usr/bin/env bash
set -euo pipefail

exec llama-server \
    -hf ggml-org/Qwen3.5-0.8B-GGUF:Q4_0 \
    --ctx-size 4096 \
    --parallel 1 \
    --reasoning off
