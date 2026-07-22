#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${1:-$SCRIPT_DIR/instances/gpu0.env}"
# shellcheck disable=SC1090
source "$ENV_FILE"

INSTANCE_NAME="${INSTANCE_NAME:-gpu${GPU_ID:-0}}"
LOG_DIR="${LOG_DIR:-$SCRIPT_DIR/logs/$INSTANCE_NAME}"

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

stop_pid_file frontend
stop_pid_file backend
stop_pid_file comfyui
echo "Instance [$INSTANCE_NAME] stopped."
