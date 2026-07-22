"""
从工作流 prompt 推导视频/媒体输出文件名。

格式: {模型名}-{图片名(若有)}-{YYYYMMDD-HHMM}
保存目录仍由 SaveVideo 的 filename_prefix 中的子路径决定（默认 video/）。
"""

from __future__ import annotations

import os
import re
import time
from typing import Any, Optional

_LOAD_IMAGE_CLASSES = frozenset({"LoadImage", "LoadImageOutput"})
_MODEL_LOADER_CLASSES = frozenset({"UNETLoader", "CheckpointLoaderSimple"})


def _sanitize_part(text: str, max_len: int = 80) -> str:
    """文件名安全片段：去扩展名、非法字符替换为 '-'。"""
    if not text:
        return ""
    base = os.path.splitext(os.path.basename(str(text).strip()))[0]
    base = base.replace(" ", "-")
    base = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", base)
    base = re.sub(r"-+", "-", base).strip("-._")
    if len(base) > max_len:
        base = base[:max_len].rstrip("-._")
    return base


def _iter_prompt_nodes(prompt: Any):
    if not isinstance(prompt, dict):
        return
    for node in prompt.values():
        if isinstance(node, dict) and node.get("class_type"):
            yield node


def extract_model_name(prompt: dict) -> str:
    """从 UNETLoader / CheckpointLoader 取主模型名（优先 high_noise）。"""
    names: list[str] = []
    for node in _iter_prompt_nodes(prompt):
        ct = node.get("class_type")
        if ct not in _MODEL_LOADER_CLASSES:
            continue
        inp = node.get("inputs") or {}
        name = inp.get("unet_name") or inp.get("ckpt_name")
        if name:
            names.append(str(name))

    if not names:
        return "model"

    for name in names:
        if "high_noise" in name.lower():
            return _sanitize_part(name)

    return _sanitize_part(names[0])


def extract_image_name(prompt: dict) -> Optional[str]:
    """从 LoadImage 取输入图片名（无扩展名）。"""
    for node in _iter_prompt_nodes(prompt):
        if node.get("class_type") not in _LOAD_IMAGE_CLASSES:
            continue
        img = (node.get("inputs") or {}).get("image")
        if img and isinstance(img, str):
            part = _sanitize_part(img)
            if part:
                return part
    return None


def format_timestamp(t: Optional[time.struct_time] = None) -> str:
    """日期-小时-分钟，例如 20250624-1530。"""
    t = t or time.localtime()
    return f"{t.tm_year:04d}{t.tm_mon:02d}{t.tm_mday:02d}-{t.tm_hour:02d}{t.tm_min:02d}"


def build_media_filename_prefix(
    prompt: dict,
    filename_prefix: str = "video/ComfyUI",
    *,
    now: Optional[time.struct_time] = None,
) -> str:
    """
    生成完整 filename_prefix（含子目录）。
    例: video/wan2.2-t2v-high-noise-14B-fp8-scaled-example-20250624-1530
    """
    model = extract_model_name(prompt)
    image = extract_image_name(prompt)
    ts = format_timestamp(now)

    parts = [model]
    if image:
        parts.append(image)
    parts.append(ts)

    name = "-".join(p for p in parts if p)

    subfolder = os.path.dirname(os.path.normpath(filename_prefix or "video"))
    if subfolder in ("", "."):
        subfolder = "video"
    return os.path.join(subfolder, name)
