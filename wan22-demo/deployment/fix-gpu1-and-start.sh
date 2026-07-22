#!/usr/bin/env bash
# 需要 sudo 密码：重启驱动/机器后，在 GPU1 上拉起全部服务
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "当前 CUDA 状态："
/home/hik/miniconda3/envs/comfyui/bin/python - <<'PY' || true
import torch
print("  is_available =", torch.cuda.is_available())
print("  device_count =", torch.cuda.device_count())
PY

echo
echo "GPU 驱动已卡死（cuInit=999 / CUDA unknown error）时，必须重启机器才能恢复。"
echo "即将执行: sudo reboot"
echo "重启后请登录，再运行:"
echo "  $SCRIPT_DIR/start-all-gpu1.sh"
echo
read -r -p "确认现在重启？输入 yes 继续: " ans
if [[ "$ans" != "yes" ]]; then
  echo "已取消。"
  exit 1
fi

sudo reboot
