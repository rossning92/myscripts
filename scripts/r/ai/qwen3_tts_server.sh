#!/usr/bin/env bash
set -euo pipefail

exec docker run --rm --init --name qwen3-tts \
    --runtime nvidia \
    -e NVIDIA_VISIBLE_DEVICES=all \
    -e NVIDIA_DRIVER_CAPABILITIES=compute,utility \
    --ipc=host \
    -p 127.0.0.1:8091:8091 \
    -v "$HOME/.cache/huggingface:/root/.cache/huggingface" \
    --entrypoint vllm \
    vllm/vllm-omni:v0.20.0 \
    serve Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice \
    --omni \
    --host 0.0.0.0 --port 8091 "$@"
