#!/usr/bin/env bash
# Start MiniMax-H3 FL2VA on a single free GPU.
# Default: GPU1 — GPU0 often holds other services (~45GB).
set -euo pipefail

MODEL_PATH="${MODEL_PATH:-/mnt/ddr1/ai-models/models-download/minimax/MiniMax-H3}"
VENV="${VENV:-/mnt/ddr2/qxk/workspace/ai-videos/.venvs/minimax-h3}"
PORT="${PORT:-30010}"
CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-1}"

if [[ -f "${VENV}/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${VENV}/bin/activate"
fi

if ! command -v sglang >/dev/null 2>&1; then
  echo "sglang not found. Install first:"
  echo "  source ${VENV}/bin/activate"
  echo "  uv pip install 'sglang[diffusion]' --prerelease=allow"
  exit 1
fi

if [[ ! -d "${MODEL_PATH}/FL2VA" ]]; then
  echo "Missing FL2VA under ${MODEL_PATH}"
  exit 1
fi

# shellcheck disable=SC1091
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/minimax-h3-auth.sh"

export CUDA_VISIBLE_DEVICES

echo "Model: ${MODEL_PATH}"
echo "CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES} (single-GPU)"
echo "Port : ${PORT}"
nvidia-smi -L || true
nvidia-smi --query-gpu=index,memory.used,memory.total --format=csv || true

# Single-GPU + layerwise offload to fit ~96GB with Qwen3-VL + DiT + VAEs.
exec sglang serve \
  --model-path "${MODEL_PATH}" \
  --model-variant fl2va \
  --num-gpus 1 \
  --tp-size 1 \
  --ulysses-degree 1 \
  --performance-mode memory \
  --layerwise-offload-components dit,text_encoder,vae \
  --dit-offload-prefetch-size 1 \
  --dit-layerwise-resident-layers 20 \
  --enable-torch-compile false \
  --host 0.0.0.0 \
  --port "${PORT}" \
  "${SGLANG_AUTH_ARGS[@]}"
