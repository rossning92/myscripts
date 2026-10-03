#!/usr/bin/env bash
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd -P)"
src="$root/repos/llama.cpp"

sudo apt-get update
sudo apt-get install -y build-essential cmake git ninja-build libcurl4-openssl-dev

cuda=OFF
if command -v nvidia-smi >/dev/null && nvidia-smi >/dev/null 2>&1; then
    if ! command -v nvcc >/dev/null; then
        sudo apt-get install -y cuda-toolkit-13-4
    fi

    for cuda_bin in /usr/local/cuda/bin /usr/local/cuda-13.4/bin; do
        if [[ -x "$cuda_bin/nvcc" ]]; then
            export PATH="$cuda_bin:$PATH"
            break
        fi
    done

    if ! command -v nvcc >/dev/null; then
        echo "NVIDIA GPU detected, but nvcc is unavailable after installing CUDA Toolkit." >&2
        exit 1
    fi
    cuda=ON
fi

if [[ ! -d "$src/.git" ]]; then
    git clone --depth 1 https://github.com/ggml-org/llama.cpp "$src"
fi

cmake -S "$src" -B "$src/build" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_SHARED_LIBS=OFF \
    -DGGML_CUDA="$cuda"
cmake --build "$src/build" --parallel "$(nproc)"
cmake --install "$src/build" --prefix "$HOME/.local"

export PATH="$HOME/.local/bin:$PATH"
llama-cli --version
echo "Installed in $HOME/.local/bin (CUDA: $cuda)"
