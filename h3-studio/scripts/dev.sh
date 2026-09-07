#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="${VENV:-/mnt/ddr2/qxk/workspace/ai-videos/.venvs/minimax-h3}"
API_PORT="${API_PORT:-8787}"
WEB_PORT="${WEB_PORT:-5173}"

# shellcheck disable=SC1091
source "${VENV}/bin/activate"

cleanup() {
  if [[ -n "${API_PID:-}" ]]; then kill "${API_PID}" 2>/dev/null || true; fi
  if [[ -n "${WEB_PID:-}" ]]; then kill "${WEB_PID}" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM

cd "${ROOT}/backend"
python -m uvicorn app.main:app --host 0.0.0.0 --port "${API_PORT}" --reload &
API_PID=$!

echo "H3 Studio  http://0.0.0.0:${API_PORT}"

# Optional Vite frontend if deps are installed.
if [[ -d "${ROOT}/frontend/node_modules/vite" ]]; then
  cd "${ROOT}/frontend"
  npm run dev -- --host 0.0.0.0 --port "${WEB_PORT}" &
  WEB_PID=$!
  echo "Vite UI     http://0.0.0.0:${WEB_PORT}"
else
  echo "Vite frontend skipped (no node_modules); use static UI on :${API_PORT}"
fi

wait
