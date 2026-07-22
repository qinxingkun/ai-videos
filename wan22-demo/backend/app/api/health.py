from __future__ import annotations

import subprocess

from fastapi import APIRouter

from app.config import get_settings
from app.services.http_client import async_client
from app.services import media_ops

router = APIRouter(tags=["health"])


async def _probe_qwen_image() -> dict | None:
    settings = get_settings()
    if not settings.qwen_image_url:
        return None
    try:
        async with async_client(timeout=3.0) as client:
            r = await client.get(settings.qwen_image_url.rstrip("/") + "/health")
            if r.status_code == 200:
                return r.json()
    except Exception:
        pass
    return {"ok": False, "url": settings.qwen_image_url}


@router.get("/health")
async def health() -> dict:
    settings = get_settings()
    ffmpeg = subprocess.run(["ffmpeg", "-version"], capture_output=True).returncode == 0
    qwen = await _probe_qwen_image()
    payload = {
        "ok": True,
        "comfyuiRoot": str(settings.comfyui_root),
        "videoDir": str(settings.video_dir),
        "ffmpeg": ffmpeg,
    }
    if qwen is not None:
        payload["qwenImage"] = qwen
    return payload


@router.get("/health/full")
async def health_full() -> dict:
    return media_ops.health_full()
