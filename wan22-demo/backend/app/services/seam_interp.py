from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.services.workflow_builder import clone_graph, force_set_input, load_workflow

WORKFLOW_REL_PATH = Path("postprocess") / "seam_interp.api.json"

NODE_IDS = {
    "loadLeft": "1",
    "loadRight": "2",
    "rife": "4",
    "saveImages": "5",
}

DEFAULTS = {
    # 接缝前后插入的中间帧数（2~4），只处理边界少量帧，计算量可控
    "num_frames": 3,
    "poll_interval_sec": 1.0,
    "timeout_sec": 90.0,
}


def workflow_path(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return settings.workflows_dir / WORKFLOW_REL_PATH


def is_configured(settings: Settings | None = None) -> bool:
    return workflow_path(settings).exists()


def _upload_image_sync(client: httpx.Client, path: Path) -> str:
    with path.open("rb") as f:
        files = {"image": (path.name, f, "image/png")}
        r = client.post("/upload/image", files=files, data={"overwrite": "true"})
    if r.status_code >= 400:
        raise RuntimeError(f"上传接缝帧失败: {r.status_code} {r.text[:200]}")
    payload = r.json()
    return payload["name"]


def _queue_prompt_sync(client: httpx.Client, graph: dict) -> str:
    client_id = str(uuid.uuid4())
    r = client.post("/prompt", json={"prompt": graph, "client_id": client_id})
    if r.status_code >= 400:
        raise RuntimeError(f"提交 RIFE 插帧工作流失败: {r.status_code} {r.text[:300]}")
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
            raise RuntimeError("RIFE 插帧执行失败（ComfyUI 报错，节点或模型可能未安装）")
        time.sleep(poll_interval_sec)
    raise RuntimeError("RIFE 插帧超时")


def _collect_output_images(entry: dict[str, Any]) -> list[dict]:
    frame_files: list[dict] = []
    for _node_id, out in (entry.get("outputs") or {}).items():
        for _key, arr in out.items():
            if isinstance(arr, list):
                for item in arr:
                    if isinstance(item, dict) and item.get("filename"):
                        frame_files.append(item)
    return frame_files


def _download_image_sync(client: httpx.Client, item: dict, out_path: Path) -> None:
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


def generate_seam_transition(
    left_frame: str | Path,
    right_frame: str | Path,
    *,
    out_clip: str | Path,
    fps: float = 24.0,
    num_frames: int | None = None,
    settings: Settings | None = None,
) -> bool:
    """用 RIFE VFI 在两张接缝边界帧之间生成若干中间帧，合成极短过渡片段替换硬切/micro-xfade。

    只处理接缝前后各 2~4 帧，不影响主生成链路。任何环节失败（工作流缺失/自定义节点或模型
    未安装/ComfyUI 未启动/超时等）都会返回 False，调用方需回退到既有 micro-xfade 处理。
    """
    settings = settings or get_settings()
    wf_path = workflow_path(settings)
    if not wf_path.exists():
        return False

    left_frame = Path(left_frame)
    right_frame = Path(right_frame)
    out_clip = Path(out_clip)
    if not left_frame.exists() or not right_frame.exists():
        return False

    n = num_frames or DEFAULTS["num_frames"]

    try:
        graph = load_workflow(wf_path)
    except Exception:
        return False

    tmp = Path(tempfile.mkdtemp(prefix="seam-rife-"))
    try:
        try:
            with httpx.Client(base_url=settings.comfyui_url, timeout=60.0) as client:
                left_name = _upload_image_sync(client, left_frame)
                right_name = _upload_image_sync(client, right_frame)

                g = clone_graph(graph)
                force_set_input(g, NODE_IDS["loadLeft"], "image", left_name)
                force_set_input(g, NODE_IDS["loadRight"], "image", right_name)
                # multiplier=n+1 时，RIFE 在两端点帧之间近似产出 n 个中间帧
                force_set_input(g, NODE_IDS["rife"], "multiplier", max(2, n + 1))
                force_set_input(
                    g, NODE_IDS["saveImages"], "filename_prefix", f"seam_rife_{uuid.uuid4().hex[:8]}"
                )

                prompt_id = _queue_prompt_sync(client, g)
                entry = _wait_history_sync(
                    client,
                    prompt_id,
                    timeout_sec=DEFAULTS["timeout_sec"],
                    poll_interval_sec=DEFAULTS["poll_interval_sec"],
                )
                frame_items = _collect_output_images(entry)
                if not frame_items:
                    return False

                frame_paths: list[Path] = []
                for i, item in enumerate(frame_items):
                    dest = tmp / f"frame_{i:04d}.png"
                    _download_image_sync(client, item, dest)
                    frame_paths.append(dest)
        except Exception:
            return False

        return _encode_frames_to_clip(frame_paths, out_clip, fps=fps)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _encode_frames_to_clip(frame_paths: list[Path], out_clip: Path, *, fps: float) -> bool:
    if not frame_paths:
        return False
    list_file = out_clip.parent / f".seam-frames-{uuid.uuid4().hex[:8]}.txt"
    seg_dur = 1.0 / max(1.0, fps)
    lines = []
    for p in frame_paths:
        lines.append(f"file '{p.as_posix()}'")
        lines.append(f"duration {seg_dur:.6f}")
    lines.append(f"file '{frame_paths[-1].as_posix()}'")
    try:
        list_file.write_text("\n".join(lines), encoding="utf-8")
        r = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(fps),
                str(out_clip),
            ],
            capture_output=True,
            text=True,
        )
        return r.returncode == 0 and out_clip.exists()
    except Exception:
        return False
    finally:
        list_file.unlink(missing_ok=True)
