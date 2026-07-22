#!/usr/bin/env bash
# Qwen-Image-2512 diffusers 推理服务（默认 :8192）
# 注意：模型约 55GB VRAM，与 ComfyUI Wan 不宜同卡同时满载运行。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$SCRIPT_DIR/logs/qwen-image"
mkdir -p "$LOG_DIR"

COMFY_PYTHON="${COMFY_PYTHON:-/home/hik/miniconda3/envs/comfyui/bin/python}"
MODEL_DIR="${QWEN_IMAGE_MODEL_DIR:-/mnt/ddr1/ai-models/models-download/qwen/Qwen-Image-2512}"
HOST="${QWEN_IMAGE_HOST:-127.0.0.1}"
PORT="${QWEN_IMAGE_PORT:-8192}"
CUDA_DEV="${CUDA_VISIBLE_DEVICES:-1}"

port_busy() { ss -ltn 2>/dev/null | rg -q ":${1}\\b"; }

if port_busy "$PORT"; then
  echo "端口 :$PORT 已被占用。若已是 Qwen-Image 服务可忽略；否则先停止占用进程。"
  curl -sf "http://${HOST}:${PORT}/health" && echo && exit 0
fi

if [[ ! -d "$MODEL_DIR" ]]; then
  echo "模型目录不存在: $MODEL_DIR" >&2
  exit 1
fi

echo "==> 启动 Qwen-Image-2512 :$PORT (CUDA_VISIBLE_DEVICES=$CUDA_DEV) ..."
nohup env \
  CUDA_VISIBLE_DEVICES="$CUDA_DEV" \
  CUDA_DEVICE_ORDER=PCI_BUS_ID \
  HF_HUB_OFFLINE=1 \
  PYTHONUNBUFFERED=1 \
  "$COMFY_PYTHON" "$PROJECT_ROOT/deployment/providers/qwen_image_server.py" \
  --model-dir "$MODEL_DIR" \
  --host "$HOST" \
  --port "$PORT" \
  >"$LOG_DIR/qwen-image.log" 2>&1 &
echo $! >"$LOG_DIR/qwen-image.pid"

echo "加载模型中（首次启动较慢，约 55GB）… 日志: $LOG_DIR/qwen-image.log"
for _ in $(seq 1 120); do
  if curl -sf "http://${HOST}:${PORT}/health" >/dev/null 2>&1; then
    echo "OK  Qwen-Image http://${HOST}:${PORT}/health"
    curl -sf "http://${HOST}:${PORT}/health"
    echo
    exit 0
  fi
  sleep 5
done

echo "仍在加载，请 tail -f $LOG_DIR/qwen-image.log" >&2
exit 0
