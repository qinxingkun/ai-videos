#!/usr/bin/env bash
# 在 GPU1 上统一启动：ComfyUI + wan22 视频生成(backend/frontend) + CosyVoice + video-concat
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKSPACE_ROOT="$(cd "$PROJECT_ROOT/.." && pwd)"
LOG_DIR="$SCRIPT_DIR/logs/gpu1-all"
mkdir -p "$LOG_DIR"

export CUDA_VISIBLE_DEVICES=1
export CUDA_DEVICE_ORDER=PCI_BUS_ID
export HF_HUB_OFFLINE=1
export PYTHONUNBUFFERED=1
export NO_PROXY=127.0.0.1,localhost
export no_proxy=127.0.0.1,localhost

COMFY_PYTHON="${COMFY_PYTHON:-/home/hik/miniconda3/envs/comfyui/bin/python}"
COSY_PYTHON="${COSY_PYTHON:-/home/hik/miniconda3/envs/cosyvoice/bin/python}"
COMFYUI_DIR="${COMFYUI_DIR:-$WORKSPACE_ROOT/ComfyUI}"

COMFY_PORT=8188
BACKEND_PORT=8190
FRONTEND_PORT=5173
COSY_PORT=8191
CONCAT_API_PORT=3040
CONCAT_UI_PORT=5180

port_busy() { ss -ltn 2>/dev/null | rg -q ":${1}\\b"; }

wait_http() {
  local url="$1" name="$2" n="${3:-60}"
  for _ in $(seq 1 "$n"); do
    if curl -sf "$url" >/dev/null 2>&1; then
      echo "  OK  $name"
      return 0
    fi
    sleep 2
  done
  echo "  FAIL $name ($url)" >&2
  return 1
}

echo "==> 检查 CUDA (GPU1) ..."
"$COMFY_PYTHON" - <<'PY'
import os, sys, torch
print(f"CUDA_VISIBLE_DEVICES={os.environ.get('CUDA_VISIBLE_DEVICES')}")
if not torch.cuda.is_available():
    print("ERROR: torch.cuda.is_available()=False", file=sys.stderr)
    print("驱动未恢复。请先执行: sudo reboot", file=sys.stderr)
    sys.exit(1)
print("CUDA OK:", torch.cuda.get_device_name(0), "count=", torch.cuda.device_count())
x = torch.zeros(1, device="cuda")
print("tensor OK on", x.device)
PY

echo "==> 停止旧进程（本机相关端口）..."
for p in "$COMFY_PORT" "$BACKEND_PORT" "$FRONTEND_PORT" "$COSY_PORT" "$CONCAT_API_PORT" "$CONCAT_UI_PORT" 8195 5174 8189; do
  if port_busy "$p"; then
    echo "  kill :$p"
    fuser -k "${p}/tcp" 2>/dev/null || true
  fi
done
# 额外清理常见残留
pkill -f "$COMFYUI_DIR/main.py" 2>/dev/null || true
pkill -f "cosyvoice_server.py" 2>/dev/null || true
pkill -f "video-concat/server/index.js" 2>/dev/null || true
pkill -f "video-concat/node_modules/.bin/vite" 2>/dev/null || true
sleep 2

echo "==> 启动 ComfyUI :$COMFY_PORT (GPU1) ..."
nohup env CUDA_VISIBLE_DEVICES=1 CUDA_DEVICE_ORDER=PCI_BUS_ID \
  "$COMFY_PYTHON" "$COMFYUI_DIR/main.py" --listen 0.0.0.0 --port "$COMFY_PORT" \
  >"$LOG_DIR/comfyui.log" 2>&1 &
echo $! >"$LOG_DIR/comfyui.pid"

echo "==> 启动 CosyVoice :$COSY_PORT (GPU1) ..."
nohup env CUDA_VISIBLE_DEVICES=1 CUDA_DEVICE_ORDER=PCI_BUS_ID HF_HUB_OFFLINE=1 \
  "$COSY_PYTHON" "$PROJECT_ROOT/deployment/providers/cosyvoice_server.py" \
  --cosyvoice-root "$WORKSPACE_ROOT/CosyVoice" \
  --model-dir "$WORKSPACE_ROOT/CosyVoice/pretrained_models/Fun-CosyVoice3-0.5B" \
  --voice-root "$PROJECT_ROOT/backend/data/voices" \
  --default-voice default.wav \
  --whisper-checkpoint "$WORKSPACE_ROOT/LatentSync/checkpoints/whisper/tiny.pt" \
  --port "$COSY_PORT" \
  >"$LOG_DIR/cosyvoice.log" 2>&1 &
echo $! >"$LOG_DIR/cosyvoice.pid"

echo "==> 启动 wan22 后端 :$BACKEND_PORT ..."
(
  cd "$PROJECT_ROOT/backend"
  # shellcheck disable=SC1091
  source .venv/bin/activate
  nohup env \
    CUDA_VISIBLE_DEVICES=1 \
    PORT="$BACKEND_PORT" \
    COMFYUI_URL="http://127.0.0.1:$COMFY_PORT" \
    COSYVOICE_URL="http://127.0.0.1:$COSY_PORT/synthesize" \
    ASR_QA_URL="http://127.0.0.1:$COSY_PORT/transcribe" \
    python main.py \
    >"$LOG_DIR/backend.log" 2>&1 &
  echo $! >"$LOG_DIR/backend.pid"
)

echo "==> 启动 wan22 前端 :$FRONTEND_PORT ..."
(
  cd "$PROJECT_ROOT/frontend"
  nohup env \
    PORT="$FRONTEND_PORT" \
    API_HOST="http://127.0.0.1:$BACKEND_PORT" \
    COMFYUI_HOST="http://127.0.0.1:$COMFY_PORT" \
    npm run dev \
    >"$LOG_DIR/frontend.log" 2>&1 &
  echo $! >"$LOG_DIR/frontend.pid"
)

echo "==> 启动 video-concat 后端 :$CONCAT_API_PORT ..."
(
  cd "$WORKSPACE_ROOT/video-concat"
  nohup env \
    PORT="$CONCAT_API_PORT" \
    COSYVOICE_URL="http://127.0.0.1:$COSY_PORT/synthesize" \
    node server/index.js \
    >"$LOG_DIR/video-concat-api.log" 2>&1 &
  echo $! >"$LOG_DIR/video-concat-api.pid"
)

echo "==> 启动 video-concat 前端 :$CONCAT_UI_PORT ..."
(
  cd "$WORKSPACE_ROOT/video-concat"
  nohup env npm run dev:client \
    >"$LOG_DIR/video-concat-ui.log" 2>&1 &
  echo $! >"$LOG_DIR/video-concat-ui.pid"
)

echo "==> 等待服务就绪 ..."
wait_http "http://127.0.0.1:$COMFY_PORT/system_stats" "ComfyUI" 90 || true
wait_http "http://127.0.0.1:$COSY_PORT/health" "CosyVoice" 90 || true
wait_http "http://127.0.0.1:$BACKEND_PORT/health" "wan22-backend" 60 || true
wait_http "http://127.0.0.1:$FRONTEND_PORT/" "wan22-frontend" 30 || true
wait_http "http://127.0.0.1:$CONCAT_API_PORT/api/health" "video-concat-api" 30 || true
wait_http "http://127.0.0.1:$CONCAT_UI_PORT/" "video-concat-ui" 30 || true

echo
echo "======== GPU1 服务已启动 ========"
echo "  视频生成 UI:   http://127.0.0.1:$FRONTEND_PORT"
echo "  视频生成 API:  http://127.0.0.1:$BACKEND_PORT/docs"
echo "  ComfyUI:       http://127.0.0.1:$COMFY_PORT"
echo "  CosyVoice:     http://127.0.0.1:$COSY_PORT/health"
echo "  视频拼接 UI:   http://127.0.0.1:$CONCAT_UI_PORT"
echo "  视频拼接 API:  http://127.0.0.1:$CONCAT_API_PORT/api/health"
echo "  日志目录:      $LOG_DIR"
echo "停止: $SCRIPT_DIR/stop-all-gpu1.sh"
echo "================================="
