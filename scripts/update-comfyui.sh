#!/usr/bin/env bash
# 一键更新 ComfyUI 官方源码，保留 models / custom_nodes / input / output / user
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMFY="$ROOT/ComfyUI"
TMP="${TMPDIR:-/tmp}/ComfyUI-upstream-$$"
ZIP="${TMPDIR:-/tmp}/ComfyUI-master-$$.zip"

cleanup() { rm -rf "$TMP" "$ZIP"; }
trap cleanup EXIT

echo ">> download upstream zip..."
ok=0
for url in \
  "${COMFYUI_ZIP_URL:-}" \
  "https://ghfast.top/https://github.com/comfyanonymous/ComfyUI/archive/refs/heads/master.zip" \
  "https://ghproxy.net/https://github.com/comfyanonymous/ComfyUI/archive/refs/heads/master.zip" \
  "https://github.com/comfyanonymous/ComfyUI/archive/refs/heads/master.zip"
 do
  [[ -z "$url" ]] && continue
  echo "   try $url"
  if curl -fL --connect-timeout 20 --max-time 300 -o "$ZIP" "$url" \
    && file "$ZIP" | grep -qi 'Zip archive'; then
    ok=1
    break
  fi
  rm -f "$ZIP"
 done
[[ "$ok" -eq 1 ]] || { echo "download failed"; exit 1; }

mkdir -p "$TMP"
unzip -q "$ZIP" -d "$TMP"
SRC="$(find "$TMP" -maxdepth 1 -type d -name 'ComfyUI-*' | head -1)"
test -f "$SRC/main.py"

echo ">> sync source (keep local assets)..."
rsync -a --delete \
  --exclude 'models/' \
  --exclude 'custom_nodes/' \
  --exclude 'input/' \
  --exclude 'output/' \
  --exclude 'user/' \
  --exclude 'temp/' \
  --exclude '.git/' \
  --exclude 'extra_model_paths.yaml' \
  --exclude '__pycache__/' \
  --exclude '*.log' \
  "$SRC/" "$COMFY/"

echo ">> pip install requirements..."
/home/hik/miniconda3/envs/comfyui/bin/pip install -r "$COMFY/requirements.txt"

echo "done. restart ComfyUI when ready."
