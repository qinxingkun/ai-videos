#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs/gpu1-all"

stop_pid_file() {
  local name="$1"
  local file="$LOG_DIR/${name}.pid"
  if [[ ! -f "$file" ]]; then
    return 0
  fi
  local pid
  pid="$(cat "$file")"
  if kill -0 "$pid" 2>/dev/null; then
    echo "Stopping $name (pid $pid)..."
    kill "$pid" 2>/dev/null || true
    sleep 1
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$file"
}

for name in frontend backend comfyui cosyvoice video-concat-ui video-concat-api; do
  stop_pid_file "$name"
done

# 兜底按端口清理
for p in 8188 8190 5173 8191 3040 5180; do
  fuser -k "${p}/tcp" 2>/dev/null || true
done

echo "GPU1-all services stopped."
