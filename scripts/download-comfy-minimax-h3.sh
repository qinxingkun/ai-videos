#!/usr/bin/env bash
# 从 ModelScope 下载 ComfyUI 用 MiniMax-H3 量化权重到对应目录
set -euo pipefail

COMFY_MODELS="${COMFY_MODELS:-/mnt/ddr2/qxk/workspace/ai-videos/ComfyUI/models}"
TMP="${TMPDIR:-/tmp}/ms-comfy-minimax-h3"
REPO="Comfy-Org/MiniMax-H3"

mkdir -p "$COMFY_MODELS"/{vae,diffusion_models,text_encoders} "$TMP"

# ModelScope 仓库内路径（Comfy-Org 惯例）
FILES=(
  "split_files/vae/minimax_h3_video_vae_fp16.safetensors"
  "split_files/vae/minimax_h3_audio_vae_fp32.safetensors"
  "split_files/diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors"
  "split_files/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
)

echo ">> download from modelscope: $REPO"
# 逐个下，失败时再试无目录前缀
for rel in "${FILES[@]}"; do
  name="$(basename "$rel")"
  dest_dir=""
  case "$rel" in
    */vae/*) dest_dir="$COMFY_MODELS/vae" ;;
    */diffusion_models/*) dest_dir="$COMFY_MODELS/diffusion_models" ;;
    */text_encoders/*) dest_dir="$COMFY_MODELS/text_encoders" ;;
  esac
  out="$dest_dir/$name"
  if [[ -f "$out" ]] && [[ $(stat -c%s "$out") -gt 1000000 ]]; then
    echo "   skip exists: $out"
    continue
  fi
  echo "   get $rel"
  if ! modelscope download "$REPO" "$rel" --local-dir "$TMP"; then
    # 有的版本不带 split_files/ 前缀
    alt="${rel#split_files/}"
    echo "   retry $alt"
    modelscope download "$REPO" "$alt" --local-dir "$TMP"
    rel="$alt"
  fi
  # 找到刚下的文件
  found="$(find "$TMP" -type f -name "$name" | head -1)"
  if [[ -z "$found" ]]; then
    echo "ERROR: not found after download: $name"
    exit 1
  fi
  mkdir -p "$dest_dir"
  mv -f "$found" "$out"
  ls -lh "$out"
done

echo "done:"
ls -lh \
  "$COMFY_MODELS/vae/minimax_h3_video_vae_fp16.safetensors" \
  "$COMFY_MODELS/vae/minimax_h3_audio_vae_fp32.safetensors" \
  "$COMFY_MODELS/diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors" \
  "$COMFY_MODELS/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
