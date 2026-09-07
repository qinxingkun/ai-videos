#!/usr/bin/env bash
# Start MiniMax-H3 Ref2VA on a single GPU (default GPU0 / port 30011).
# Ensure the target GPU has enough free VRAM before launching.
set -euo pipefail

MODEL_PATH="${MODEL_PATH:-/mnt/ddr1/ai-models/models-download/minimax/MiniMax-H3}"
VENV="${VENV:-/mnt/ddr2/qxk/workspace/ai-videos/.venvs/minimax-h3}"
PORT="${PORT:-30011}"
CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

if [[ -f "${VENV}/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${VENV}/bin/activate"
fi

if ! command -v sglang >/dev/null 2>&1; then
  echo "sglang not found in ${VENV}"
  exit 1
fi

if [[ ! -d "${MODEL_PATH}/Ref2VA" ]]; then
  echo "Missing Ref2VA under ${MODEL_PATH}"
  exit 1
fi

# shellcheck disable=SC1091
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/scripts/minimax-h3-auth.sh"

export CUDA_VISIBLE_DEVICES

echo "Model: ${MODEL_PATH}"
echo "CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES} (Ref2VA single-GPU)"
echo "Port : ${PORT}"
nvidia-smi -L || true

exec sglang serve \
  --model-path "${MODEL_PATH}" \
  --model-variant ref2va \
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
