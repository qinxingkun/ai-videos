from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import httpx

from app.config import Settings, get_settings
from app.services.animate_relock import (
    _download_sync,
    _queue_prompt_sync,
    _upload_file_sync,
    _wait_history_sync,
)
from app.services.workflow_builder import (
    clone_graph,
    extract_media_from_history,
    force_set_input,
    load_workflow,
)
from app.services.media_probe import probe_media

MASTER_FPS = 25
RIFE_WORKFLOW = Path("postprocess") / "visual_master_rife.api.json"


async def _run(args: list[str]) -> None:
    process = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    if process.returncode:
        raise RuntimeError((stderr or stdout).decode(errors="replace")[-1000:])


def _try_comfy_rife(source: Path, output: Path, settings: Settings) -> bool:
    """Run the repository's full-clip ComfyUI RIFE workflow when available."""
    workflow = settings.workflows_dir / RIFE_WORKFLOW
    if not workflow.exists():
        return False
    try:
        graph = clone_graph(load_workflow(workflow))
        with httpx.Client(base_url=settings.comfyui_url, timeout=60.0) as client:
            uploaded = _upload_file_sync(client, source, mime="video/mp4")
            force_set_input(graph, "1", "video", uploaded)
            force_set_input(graph, "3", "filename_prefix", f"visual_master_rife_{uuid.uuid4().hex[:8]}")
            prompt_id = _queue_prompt_sync(client, graph)
            entry = _wait_history_sync(
                client,
                prompt_id,
                timeout_sec=max(300, settings.provider_timeout_sec),
                poll_interval_sec=1,
            )
            media = extract_media_from_history({prompt_id: entry}, prompt_id)
            videos = [item for item in media if item.get("kind") == "video"]
            if not videos:
                return False
            _download_sync(client, videos[0], output)
            return output.exists() and output.stat().st_size > 0
    except Exception:
        return False


async def create_visual_master(
    source: str | Path,
    output: str | Path,
    *,
    settings: Settings | None = None,
) -> dict:
    settings = settings or get_settings()
    source = Path(source)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    rife_tmp = output.with_name(f".{output.stem}.rife.mp4")
    source_duration = float(probe_media(source).get("duration") or 0)
    if source_duration <= 0:
        raise RuntimeError("source video duration is invalid")
    expected_frames = round(source_duration * MASTER_FPS)
    applied = False
    if settings.visual_master_rife_enabled:
        applied = await asyncio.to_thread(_try_comfy_rife, source, rife_tmp, settings)
    selected = rife_tmp if applied else source
    selected_duration = float(probe_media(selected).get("duration") or source_duration)
    pts_scale = source_duration / selected_duration if selected_duration > 0 else 1.0
    await _run(
        [
            "ffmpeg", "-y", "-i", str(selected), "-map", "0:v:0", "-an",
            "-vf",
            f"setpts={pts_scale:.12f}*PTS,fps={MASTER_FPS},setpts=PTS-STARTPTS",
            "-frames:v", str(expected_frames),
            "-fps_mode", "cfr", "-r", str(MASTER_FPS),
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p", str(output),
        ]
    )
    rife_tmp.unlink(missing_ok=True)
    return {
        "path": str(output),
        "fps": MASTER_FPS,
        "ptsStart": 0,
        "sourceDuration": source_duration,
        "expectedFrames": expected_frames,
        "method": "comfyui-rife" if applied else "ffmpeg-cfr-fallback",
        "degraded": not applied,
        "degradationReason": None if applied else "ComfyUI full-clip RIFE unavailable",
    }
