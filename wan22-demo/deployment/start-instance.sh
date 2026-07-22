#!/usr/bin/env bash
# 启动一套独立的 ComfyUI + wan22-demo 后端 + 前端（可指定 GPU 与端口）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKSPACE_ROOT="$(cd "$PROJECT_ROOT/.." && pwd)"

ENV_FILE="${1:-$SCRIPT_DIR/instances/gpu0.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Env file not found: $ENV_FILE" >&2
  exit 1
fi
# shellcheck disable=SC1090
source "$ENV_FILE"

GPU_ID="${GPU_ID:?GPU_ID required}"
COMFY_PORT="${COMFY_PORT:?COMFY_PORT required}"
BACKEND_PORT="${BACKEND_PORT:?BACKEND_PORT required}"
FRONTEND_PORT="${FRONTEND_PORT:?FRONTEND_PORT required}"
COMFYUI_URL="${COMFYUI_URL:-http://127.0.0.1:$COMFY_PORT}"

COMFYUI_DIR="${COMFYUI_DIR:-$WORKSPACE_ROOT/ComfyUI}"
COMFY_PYTHON="${COMFY_PYTHON:-}"
if [[ -z "$COMFY_PYTHON" ]]; then
  if [[ -x /home/hik/miniconda3/envs/comfyui/bin/python ]]; then
    COMFY_PYTHON=/home/hik/miniconda3/envs/comfyui/bin/python
  else
    COMFY_PYTHON=python
  fi
fi

INSTANCE_NAME="${INSTANCE_NAME:-gpu${GPU_ID}}"
LOG_DIR="${LOG_DIR:-$SCRIPT_DIR/logs/$INSTANCE_NAME}"
mkdir -p "$LOG_DIR"

port_busy() {
  ss -ltn 2>/dev/null | rg -q ":${1} "
}

for p in "$COMFY_PORT" "$BACKEND_PORT" "$FRONTEND_PORT"; do
  if port_busy "$p"; then
    echo "Port $p is already in use. Stop the existing service or change ports in $ENV_FILE" >&2
    exit 1
  fi
done

if [[ ! -f "$COMFYUI_DIR/main.py" ]]; then
  echo "ComfyUI not found at $COMFYUI_DIR" >&2
  exit 1
fi

echo "Starting wan22-demo instance [$INSTANCE_NAME] on GPU $GPU_ID ..."
echo "  ComfyUI  -> :$COMFY_PORT"
echo "  Backend  -> :$BACKEND_PORT"
echo "  Frontend -> :$FRONTEND_PORT"
echo "  Logs     -> $LOG_DIR"

nohup env CUDA_VISIBLE_DEVICES="$GPU_ID" "$COMFY_PYTHON" "$COMFYUI_DIR/main.py" \
  --listen 0.0.0.0 --port "$COMFY_PORT" \
  >"$LOG_DIR/comfyui.log" 2>&1 &
echo $! >"$LOG_DIR/comfyui.pid"

sleep 2
if ! kill -0 "$(cat "$LOG_DIR/comfyui.pid")" 2>/dev/null; then
  echo "ComfyUI failed to start. See $LOG_DIR/comfyui.log" >&2
  tail -20 "$LOG_DIR/comfyui.log" >&2 || true
  exit 1
fi

(
  cd "$PROJECT_ROOT/backend"
  # shellcheck disable=SC1091
  source .venv/bin/activate
  nohup env PORT="$BACKEND_PORT" COMFYUI_URL="$COMFYUI_URL" python main.py \
    >"$LOG_DIR/backend.log" 2>&1 &
  echo $! >"$LOG_DIR/backend.pid"
)

sleep 1
if ! kill -0 "$(cat "$LOG_DIR/backend.pid")" 2>/dev/null; then
  echo "Backend failed to start. See $LOG_DIR/backend.log" >&2
  tail -20 "$LOG_DIR/backend.log" >&2 || true
  exit 1
fi

(
  cd "$PROJECT_ROOT/frontend"
  nohup env PORT="$FRONTEND_PORT" \
    API_HOST="http://127.0.0.1:$BACKEND_PORT" \
    COMFYUI_HOST="$COMFYUI_URL" \
    npm run dev \
    >"$LOG_DIR/frontend.log" 2>&1 &
  echo $! >"$LOG_DIR/frontend.pid"
)

for _ in $(seq 1 20); do
  if curl -sf "http://127.0.0.1:$BACKEND_PORT/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo
echo "Ready:"
echo "  UI:      http://127.0.0.1:$FRONTEND_PORT"
echo "  API:     http://127.0.0.1:$BACKEND_PORT/docs"
echo "  ComfyUI: http://127.0.0.1:$COMFY_PORT"
echo
echo "Stop with: deployment/stop-instance.sh $ENV_FILE"
