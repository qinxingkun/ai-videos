"""InstantID 定妆照 / 段首帧生产（阶段 0）。

用 1 张参考脸 + 文案生成稳定身份资产，供 VACE `ref_images` 与 Animate `ref_images` 共用。
依赖 ComfyUI_InstantID + SDXL + antelopev2；任一缺失时返回清晰错误，不静默假成功。
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.services.workflow_builder import clone_graph, extract_media_from_history, force_set_input, load_workflow

WORKFLOW_REL_PATH = Path("instantid_lookbook.api.json")

NODE_IDS = {
    "loadFace": "13",
    "positive": "39",
    "negative": "40",
    "sampler": "3",
    "latent": "5",
    "save": "9",
}

DEFAULTS = {
    "poll_interval_sec": 2.0,
    "timeout_sec": 600.0,
    "width": 1016,
    "height": 1016,
    "steps": 30,
    "cfg": 4.5,
}


def workflow_path(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return settings.workflows_dir / WORKFLOW_REL_PATH


def is_configured(settings: Settings | None = None) -> bool:
    return not missing_components(settings)


def missing_components(settings: Settings | None = None) -> list[str]:
    settings = settings or get_settings()
    root = settings.comfyui_root
    antelope = root / "models" / "insightface" / "models" / "antelopev2"
    antelope_ok = antelope.is_dir() and any(antelope.glob("*.onnx"))
    mapping = {
        "ComfyUI_InstantID 节点": root / "custom_nodes" / "ComfyUI_InstantID",
        "ip-adapter.bin": root / "models" / "instantid" / "ip-adapter.bin",
        "instantid_controlnet.safetensors": root / "models" / "controlnet" / "instantid_controlnet.safetensors",
        "antelopev2": antelope if antelope_ok else Path("/__missing_antelopev2__"),
        "sd_xl_base_1.0.safetensors": root / "models" / "checkpoints" / "sd_xl_base_1.0.safetensors",
        "工作流 instantid_lookbook.api.json": workflow_path(settings),
    }
    missing = []
    for name, path in mapping.items():
        if name == "antelopev2":
            if not antelope_ok:
                missing.append(name)
            continue
        if not path.exists():
            missing.append(name)
    return missing


def _queue_prompt_sync(client: httpx.Client, graph: dict) -> str:
    client_id = str(uuid.uuid4())
    r = client.post("/prompt", json={"prompt": graph, "client_id": client_id})
    if r.status_code >= 400:
        raise RuntimeError(f"提交 InstantID 定妆照工作流失败: {r.status_code} {r.text[:300]}")
    prompt_id = (r.json() or {}).get("prompt_id")
    if not prompt_id:
        raise RuntimeError("ComfyUI 未返回 prompt_id")
    return prompt_id


def _wait_history_sync(
    client: httpx.Client, prompt_id: str, *, timeout_sec: float, poll_interval_sec: float
) -> dict[str, Any]:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        r = client.get(f"/history/{prompt_id}")
        r.raise_for_status()
        entry = (r.json() or {}).get(prompt_id)
        if entry and entry.get("outputs"):
            return entry
        if entry and (entry.get("status") or {}).get("status_str") == "error":
            raise RuntimeError("InstantID 定妆照执行失败（检查 SDXL/InstantID/antelopev2 是否已安装）")
        time.sleep(poll_interval_sec)
    raise RuntimeError("InstantID 定妆照超时")


def generate_lookbook(
    *,
    face_image_name: str,
    prompt: str,
    negative_prompt: str = "",
    seed: int | None = None,
    width: int | None = None,
    height: int | None = None,
    steps: int | None = None,
    cfg: float | None = None,
    filename_prefix: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """同步跑 InstantID 定妆照，返回 Comfy 输出媒体条目。"""
    settings = settings or get_settings()
    missing = missing_components(settings)
    if missing:
        raise RuntimeError("InstantID 未就绪，缺少: " + ", ".join(missing))

    face_path = settings.input_dir / face_image_name
    if not face_path.is_file():
        raise RuntimeError(f"参考脸不存在于 input/: {face_image_name}")

    graph = clone_graph(load_workflow(workflow_path(settings)))
    force_set_input(graph, NODE_IDS["loadFace"], "image", face_image_name)
    force_set_input(graph, NODE_IDS["positive"], "text", prompt or "")
    if negative_prompt:
        force_set_input(graph, NODE_IDS["negative"], "text", negative_prompt)
    force_set_input(graph, NODE_IDS["latent"], "width", int(width or DEFAULTS["width"]))
    force_set_input(graph, NODE_IDS["latent"], "height", int(height or DEFAULTS["height"]))
    force_set_input(graph, NODE_IDS["sampler"], "steps", int(steps or DEFAULTS["steps"]))
    force_set_input(graph, NODE_IDS["sampler"], "cfg", float(cfg if cfg is not None else DEFAULTS["cfg"]))
    if seed is not None:
        force_set_input(graph, NODE_IDS["sampler"], "seed", int(seed))
    prefix = filename_prefix or f"lookbook/instantid_{uuid.uuid4().hex[:8]}"
    force_set_input(graph, NODE_IDS["save"], "filename_prefix", prefix)

    with httpx.Client(base_url=settings.comfyui_url, timeout=60.0) as client:
        prompt_id = _queue_prompt_sync(client, graph)
        entry = _wait_history_sync(
            client,
            prompt_id,
            timeout_sec=DEFAULTS["timeout_sec"],
            poll_interval_sec=DEFAULTS["poll_interval_sec"],
        )
        media = extract_media_from_history({prompt_id: entry}, prompt_id)
        images = [m for m in media if m.get("kind") == "image"]
        if not images:
            # SaveImage 有时只在 outputs 里给 images 列表
            outputs = entry.get("outputs") or {}
            save_out = outputs.get(NODE_IDS["save"]) or {}
            for item in save_out.get("images") or []:
                images.append(
                    {
                        "kind": "image",
                        "filename": item.get("filename"),
                        "subfolder": item.get("subfolder") or "",
                        "type": item.get("type") or "output",
                    }
                )
        if not images:
            raise RuntimeError("InstantID 未产出定妆照")
        return {"prompt_id": prompt_id, "media": images, "lookbook": images[0]}
