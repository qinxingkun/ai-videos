#!/usr/bin/env bash
# InstantID + Wan-VACE 权重安装（国内建议 HF_ENDPOINT=https://hf-mirror.com）
# 用法：env -u HTTP_PROXY -u HTTPS_PROXY HF_ENDPOINT=https://hf-mirror.com bash scripts/install_face_consistency_weights.sh
set -euo pipefail

COMFY="${COMFYUI_ROOT:-$(cd "$(dirname "$0")/../../ComfyUI" && pwd)}"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
export NO_PROXY="${NO_PROXY:-*}"
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy || true

mkdir -p \
  "$COMFY/models/instantid" \
  "$COMFY/models/controlnet" \
  "$COMFY/models/insightface/models/antelopev2" \
  "$COMFY/models/diffusion_models" \
  "$COMFY/models/checkpoints"

if [ ! -d "$COMFY/custom_nodes/ComfyUI_InstantID" ]; then
  git clone --depth 1 https://github.com/cubiq/ComfyUI_InstantID.git "$COMFY/custom_nodes/ComfyUI_InstantID"
fi

hf download InstantX/InstantID ip-adapter.bin --local-dir "$COMFY/models/instantid"
hf download InstantX/InstantID ControlNetModel/diffusion_pytorch_model.safetensors --local-dir /tmp/instantid-cn-install
CN=$(find /tmp/instantid-cn-install -name diffusion_pytorch_model.safetensors | head -1)
cp -f "$CN" "$COMFY/models/controlnet/instantid_controlnet.safetensors"

hf download MonsterMMORPG/tools \
  1k3d68.onnx 2d106det.onnx genderage.onnx glintr100.onnx scrfd_10g_bnkps.onnx \
  --local-dir "$COMFY/models/insightface/models/antelopev2"

hf download stabilityai/stable-diffusion-xl-base-1.0 sd_xl_base_1.0.safetensors \
  --local-dir "$COMFY/models/checkpoints"

hf download Kijai/WanVideo_comfy Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors \
  --local-dir "$COMFY/models/diffusion_models"
hf download Kijai/WanVideo_comfy Wan2_1-T2V-14B_fp8_e4m3fn.safetensors \
  --local-dir "$COMFY/models/diffusion_models"

echo "Done. Restart ComfyUI to load ComfyUI_InstantID. See docs/FACE_CONSISTENCY_SOP.md"
