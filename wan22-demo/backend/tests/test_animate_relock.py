"""阶段四（可选）：Wan2.2-Animate 关键镜头身份锁定重渲染，必须在未安装/失败时优雅回退。"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.config import Settings
from app.services import media_ops
from app.services.animate_relock import generate_identity_relock


def _make_clip(path: Path, *, color: str = "red", seconds: float = 1.0) -> None:
    args = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c={color}:s=768x512:d={seconds}:r=24",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(path),
    ]
    r = subprocess.run(args, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-400:]


@pytest.fixture()
def comfy_root(tmp_path: Path) -> Path:
    root = tmp_path / "ComfyUI"
    (root / "output" / "video").mkdir(parents=True)
    (root / "input").mkdir(parents=True)
    return root


def test_returns_false_when_workflow_missing(tmp_path: Path):
    driving = tmp_path / "driving.mp4"
    ref = tmp_path / "ref.png"
    _make_clip(driving)
    ref.write_bytes(b"\x89PNG\r\n\x1a\n")
    settings = Settings(comfyui_root=tmp_path / "ComfyUI", workflows_dir=tmp_path / "no-workflows")
    ok = generate_identity_relock(driving, ref, out_path=tmp_path / "out.mp4", settings=settings)
    assert ok is False


def test_returns_false_when_inputs_missing(tmp_path: Path):
    settings = Settings(comfyui_root=tmp_path / "ComfyUI")
    ok = generate_identity_relock(
        tmp_path / "missing.mp4", tmp_path / "missing.png", out_path=tmp_path / "out.mp4", settings=settings
    )
    assert ok is False


def test_media_ops_animate_relock_falls_back_when_unavailable(monkeypatch, comfy_root: Path):
    settings = Settings(comfyui_root=comfy_root)
    video = settings.video_dir / "seg0.mp4"
    _make_clip(video)
    ref = settings.input_dir / "hero_ref.png"
    ref.write_bytes(b"\x89PNG\r\n\x1a\n")

    monkeypatch.setattr("app.services.media_ops.generate_identity_relock", lambda *a, **k: False)
    result = media_ops.animate_relock(
        {"filename": "seg0.mp4", "referenceImageName": "hero_ref.png"},
        settings=settings,
    )
    assert result["applied"] is False
    assert result["filename"] == "seg0.mp4"
    assert Path(result["path"]) == video


def test_media_ops_animate_relock_success(monkeypatch, comfy_root: Path):
    settings = Settings(comfyui_root=comfy_root)
    video = settings.video_dir / "seg0.mp4"
    _make_clip(video)
    ref = settings.input_dir / "hero_ref.png"
    ref.write_bytes(b"\x89PNG\r\n\x1a\n")

    def _fake_relock(driving_video, reference_image, *, out_path, seed=None, settings=None):
        Path(out_path).write_bytes(b"fake-relocked-video-bytes")
        return True

    monkeypatch.setattr("app.services.media_ops.generate_identity_relock", _fake_relock)
    result = media_ops.animate_relock(
        {"filename": "seg0.mp4", "referenceImageName": "hero_ref.png", "seed": 42},
        settings=settings,
    )
    assert result["applied"] is True
    assert Path(result["path"]).exists()
    assert result["filename"] != "seg0.mp4"


def test_media_ops_animate_relock_requires_reference(comfy_root: Path):
    settings = Settings(comfyui_root=comfy_root)
    video = settings.video_dir / "seg0.mp4"
    _make_clip(video)
    with pytest.raises(RuntimeError):
        media_ops.animate_relock({"filename": "seg0.mp4"}, settings=settings)


def test_animate_relock_workflow_is_wan_16fps_81_frames_1280x720():
    """与 Wan 多分镜 5s 段对齐：1280×720 @ 16fps × 81（见 docs/FACE_CONSISTENCY_SOP.md）。"""
    workflow = Path(__file__).resolve().parents[1] / "workflows" / "postprocess" / "animate_relock.api.json"
    import json

    graph = json.loads(workflow.read_text(encoding="utf-8"))
    assert graph["1"]["inputs"]["force_rate"] == 16
    assert graph["1"]["inputs"]["custom_width"] == 1280
    assert graph["1"]["inputs"]["custom_height"] == 720
    assert graph["7"]["inputs"]["width"] == 1280
    assert graph["7"]["inputs"]["height"] == 720
    assert graph["7"]["inputs"]["num_frames"] == 81
    assert graph["10"]["inputs"]["frame_rate"] == 16
