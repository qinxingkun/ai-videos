"""Wan2.2-Animate 关键镜头身份锁定重渲染（阶段四，可选增强）。

把已生成分段视频当"驱动视频"，配合角色定妆照做身份重锁定二次渲染：画面运动/构图不变，
人脸与外观强制贴合参考图。全程使用官方已发布的 Wan2.2-Animate 预训练权重
（通过社区 ComfyUI-WanVideoWrapper 节点调用），不训练专属模型。

默认关闭，仅对使用者标记的"关键镜头"（如首尾段/特写）生效；该段生成耗时会翻倍
（多一次推理），因此定位为可选增强而非默认路径。任何环节失败（自定义节点/模型未安装、
ComfyUI 未启动、超时等）都会返回 False，调用方需回退到第一遍生成的原始分段。
"""

from __future__ import annotations

import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.services.workflow_builder import clone_graph, extract_media_from_history, force_set_input, load_workflow

WORKFLOW_REL_PATH = Path("postprocess") / "animate_relock.api.json"

NODE_IDS = {
    "loadDrivingVideo": "1",
    "loadReferenceImage": "2",
    "sampler": "8",
    "saveVideo": "10",
}

DEFAULTS = {
    "poll_interval_sec": 2.0,
    # 身份重锁定是额外一次完整推理，超时窗口需明显大于普通单段生成
    "timeout_sec": 600.0,
}


def workflow_path(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return settings.workflows_dir / WORKFLOW_REL_PATH


def is_configured(settings: Settings | None = None) -> bool:
    return workflow_path(settings).exists()


def _upload_file_sync(client: httpx.Client, path: Path, *, mime: str) -> str:
    with path.open("rb") as f:
        files = {"image": (path.name, f, mime)}
        r = client.post("/upload/image", files=files, data={"overwrite": "true"})
    if r.status_code >= 400:
        raise RuntimeError(f"上传身份锁定素材失败: {r.status_code} {r.text[:200]}")
    payload = r.json()
    return payload["name"]


def _queue_prompt_sync(client: httpx.Client, graph: dict) -> str:
    client_id = str(uuid.uuid4())
    r = client.post("/prompt", json={"prompt": graph, "client_id": client_id})
    if r.status_code >= 400:
        raise RuntimeError(f"提交身份锁定重渲染工作流失败: {r.status_code} {r.text[:300]}")
    data = r.json()
    prompt_id = data.get("prompt_id")
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
        data = r.json()
        entry = data.get(prompt_id)
        if entry and entry.get("outputs"):
            return entry
        if entry and (entry.get("status") or {}).get("status_str") == "error":
            raise RuntimeError("身份锁定重渲染执行失败（WanVideoWrapper/Wan2.2-Animate 权重可能未安装）")
        time.sleep(poll_interval_sec)
    raise RuntimeError("身份锁定重渲染超时")


def _download_sync(client: httpx.Client, item: dict, out_path: Path) -> None:
    r = client.get(
        "/view",
        params={
            "filename": item["filename"],
            "subfolder": item.get("subfolder") or "",
            "type": item.get("type") or "output",
        },
    )
    r.raise_for_status()
    out_path.write_bytes(r.content)


def generate_identity_relock(
    driving_video: str | Path,
    reference_image: str | Path,
    *,
    out_path: str | Path,
    seed: int | None = None,
    settings: Settings | None = None,
) -> bool:
    """对单个关键分段做身份重锁定二次渲染，成功写出 out_path 并返回 True。

    任何失败都返回 False（不抛出），调用方据此回退到原始分段，不阻断主流程。
    """
    settings = settings or get_settings()
    wf_path = workflow_path(settings)
    if not wf_path.exists():
        return False

    driving_video = Path(driving_video)
    reference_image = Path(reference_image)
    out_path = Path(out_path)
    if not driving_video.exists() or not reference_image.exists():
        return False

    try:
        graph = load_workflow(wf_path)
    except Exception:
        return False

    tmp = Path(tempfile.mkdtemp(prefix="animate-relock-"))
    try:
        try:
            with httpx.Client(base_url=settings.comfyui_url, timeout=60.0) as client:
                video_name = _upload_file_sync(client, driving_video, mime="video/mp4")
                image_name = _upload_file_sync(client, reference_image, mime="image/png")

                g = clone_graph(graph)
                force_set_input(g, NODE_IDS["loadDrivingVideo"], "video", video_name)
                force_set_input(g, NODE_IDS["loadReferenceImage"], "image", image_name)
                if seed is not None:
                    force_set_input(g, NODE_IDS["sampler"], "seed", int(seed))
                force_set_input(
                    g, NODE_IDS["saveVideo"], "filename_prefix", f"animate_relock_{uuid.uuid4().hex[:8]}"
                )

                prompt_id = _queue_prompt_sync(client, g)
                entry = _wait_history_sync(
                    client,
                    prompt_id,
                    timeout_sec=DEFAULTS["timeout_sec"],
                    poll_interval_sec=DEFAULTS["poll_interval_sec"],
                )
                media = extract_media_from_history({prompt_id: entry}, prompt_id)
                video_items = [m for m in media if m.get("kind") == "video"]
                if not video_items:
                    return False
                _download_sync(client, video_items[0], out_path)
        except Exception:
            return False

        return out_path.exists() and out_path.stat().st_size > 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
