#!/usr/bin/env bash
set -euo pipefail

venv_dir="${SGLANG_VENV:-$HOME/.venvs/sglang}"
model_path="${SGLANG_MODEL_PATH:-$HOME/models/Qwen3.8-27B-FP8}"
model_repo="${SGLANG_MODEL_REPO:-Qwen/Qwen3.8-27B-FP8}"

uv_bin="${UV_BIN:-}"
if [[ -z "$uv_bin" ]]; then
    uv_bin="$(command -v uv || true)"
fi
if [[ -z "$uv_bin" && -x "$HOME/.local/bin/uv" ]]; then
    uv_bin="$HOME/.local/bin/uv"
fi
if [[ -z "$uv_bin" ]]; then
    echo "uv is required: https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 1
fi

sglang_bin="${SGLANG_BIN:-$venv_dir/bin/sglang}"
if [[ ! -x "$sglang_bin" ]]; then
    "$uv_bin" venv --python 3.12 "$venv_dir"
    "$uv_bin" pip install \
        --python "$venv_dir/bin/python" \
        --prerelease=allow \
        "sglang==0.5.22"
fi

if [[ ! -f "$model_path/model.safetensors.index.json" ]]; then
    "$venv_dir/bin/hf" download "$model_repo" --local-dir "$model_path"
fi

exec "$sglang_bin" serve \
    --model-path "$model_path" \
    --served-model-name "${SGLANG_MODEL:-qwen3.8-27b}" \
    --host 127.0.0.1 \
    --port "${SGLANG_PORT:-30000}" \
    --context-length 131072 \
    --max-running-requests 1 \
    --mem-fraction-static 0.96 \
    --kv-cache-dtype fp8_e4m3 \
    --mamba-ssm-dtype bfloat16 \
    --mamba-radix-cache-strategy extra_buffer_lazy \
    --max-mamba-cache-size 4 \
    --chunked-prefill-size 2048 \
    --attention-backend flashinfer \
    --reasoning-parser qwen3 \
    --tool-call-parser qwen3_coder \
    --speculative-algorithm EAGLE \
    --speculative-num-steps 3 \
    --speculative-eagle-topk 1 \
    --speculative-num-draft-tokens 4 \
    --enable-linear-replayssm-spec
