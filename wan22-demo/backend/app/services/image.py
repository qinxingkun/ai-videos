from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.http_client import async_client
from app.config import get_settings
from app.services.task_store import task_store

ASPECT_PRESETS = {
    "1:1": (1328, 1328),
    "16:9": (1664, 928),
    "9:16": (928, 1664),
    "4:3": (1472, 1104),
    "3:4": (1104, 1472),
    "3:2": (1584, 1056),
    "2:3": (1056, 1584),
}


def _resolve_size(args: dict[str, Any]) -> tuple[int, int]:
    ratio = args.get("aspect_ratio") or args.get("aspectRatio")
    if ratio and ratio in ASPECT_PRESETS:
        return ASPECT_PRESETS[ratio]
    return int(args.get("width") or 1328), int(args.get("height") or 1328)


def _output_dir() -> Path:
    settings = get_settings()
    out = settings.comfyui_root / "output"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _filename(prefix: str | None) -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = (prefix or "qwen_t2i").replace("/", "_").strip("_") or "qwen_t2i"
    return f"{base}-{stamp}_{uuid.uuid4().hex[:6]}.png"


async def _call_provider(body: dict[str, Any]) -> bytes:
    settings = get_settings()
    if not settings.qwen_image_url:
        raise RuntimeError(
            "Qwen-Image 推理服务未配置。请启动 deployment/providers/qwen_image_server.py "
            "并在 backend .env 设置 QWEN_IMAGE_URL=http://127.0.0.1:8192"
        )
    url = settings.qwen_image_url.rstrip("/") + "/generate"
    timeout = httpx.Timeout(settings.provider_timeout_sec)
    async with async_client(timeout=timeout) as client:
        r = await client.post(url, json=body)
        if r.status_code >= 400:
            detail = r.text[:500]
            try:
                detail = r.json().get("detail", detail)
            except Exception:
                pass
            raise RuntimeError(str(detail))
        return r.content


async def _run_job(task_id: str, body: dict[str, Any]) -> None:
    task_store.update(task_id, status="running", progress={"value": 0, "max": 1})
    try:
        png = await _call_provider(body)
        filename = _filename(body.get("filename_prefix"))
        path = _output_dir() / filename
        path.write_bytes(png)
        media = [{
            "kind": "image",
            "filename": filename,
            "subfolder": "",
            "type": "output",
        }]
        task_store.update(
            task_id,
            status="completed",
            media=media,
            progress={"value": 1, "max": 1},
            error=None,
        )
    except Exception as exc:
        task_store.update(task_id, status="failed", error=str(exc))


async def generate_image_t2i(args: dict[str, Any]) -> dict:
    turbo = bool(args.get("turbo"))
    width, height = _resolve_size(args)
    steps = 4 if turbo else int(args.get("steps") or 50)
    cfg = 1.0 if turbo else float(args.get("cfg") if args.get("cfg") is not None else 4.0)
    body = {
        "prompt": args.get("prompt") or args.get("positivePrompt") or "",
        "negative_prompt": args.get("negative_prompt") or args.get("negativePrompt") or "",
        "width": width,
        "height": height,
        "seed": args.get("seed"),
        "steps": steps,
        "cfg": cfg,
        "turbo": turbo,
        "filename_prefix": args.get("filename_prefix") or args.get("filenamePrefix") or "qwen_t2i",
    }
    if not body["prompt"].strip():
        raise ValueError("prompt required")

    prompt_id = f"img_{uuid.uuid4().hex}"
    client_id = f"qwen_{uuid.uuid4().hex[:8]}"
    task_id = task_store.create(
        prompt_id,
        client_id,
        meta={"engine": "qwen", "mode": "t2i", "provider": "diffusers"},
    )
    asyncio.create_task(_run_job(task_id, body))
    return {
        "task_id": task_id,
        "prompt_id": prompt_id,
        "client_id": client_id,
        "status": "queued",
        "meta": {"engine": "qwen", "mode": "t2i"},
    }


async def get_image_task(args: dict[str, Any]) -> dict:
    task_id = args.get("task_id")
    if not task_id:
        raise ValueError("task_id required")
    task = task_store.get(task_id)
    if not task:
        raise ValueError(f"unknown task_id: {task_id}")

    if task.get("status") in {"completed", "failed"}:
        media = task.get("media") or []
        if media and task.get("status") == "completed":
            settings = get_settings()
            enriched = []
            for item in media:
                row = dict(item)
                params = urlencode({
                    "filename": row["filename"],
                    "subfolder": row.get("subfolder") or "",
                    "type": row.get("type") or "output",
                })
                row["url"] = f"/v1/media/view?{params}"
                row["comfy_url"] = f"{settings.comfyui_url.rstrip('/')}/view?{params}"
                enriched.append(row)
            return {**task, "media": enriched}
        return task

    # Still running — expose elapsed for UI
    created = float(task.get("created_at") or time.time())
    return {
        **task,
        "status": task.get("status") or "running",
        "elapsed_sec": max(0, int(time.time() - created)),
    }
