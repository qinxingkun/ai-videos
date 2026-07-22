"""RIFE 接缝插帧集成：验证 ffmpeg 过渡片段拼接图正确，且失败时能优雅回退。"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.services.concat_video import concat_videos
from app.services.media_probe import probe_media
from app.services.splice_analysis import analyze_splice


def _make_clip(path: Path, *, color: str, seconds: float = 1.2) -> None:
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
def silent_clips(tmp_path: Path):
    clips = []
    for i, color in enumerate(["red", "green", "blue"]):
        p = tmp_path / f"seg{i}.mp4"
        _make_clip(p, color=color, seconds=1.2)
        clips.append(p)
    return clips


def _fake_generate_seam_transition(left_frame, right_frame, *, out_clip, fps=24.0, num_frames=3, settings=None):
    """模拟 RIFE 输出：直接合成一小段灰色过渡片段，验证拼接管线而不依赖真实 ComfyUI。"""
    args = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=gray:s=768x512:d={(num_frames + 1) / fps:.4f}:r={fps}",
        "-pix_fmt",
        "yuv420p",
        str(out_clip),
    ]
    r = subprocess.run(args, capture_output=True, text=True)
    return r.returncode == 0 and Path(out_clip).exists()


def test_smart_splice_with_seam_interp_success(monkeypatch, silent_clips, tmp_path: Path):
    monkeypatch.setattr(
        "app.services.concat_video.generate_seam_transition", _fake_generate_seam_transition
    )
    plan = analyze_splice([str(p) for p in silent_clips], fps=24, max_frames=6)
    result = concat_videos(
        [p.name for p in silent_clips],
        input_dir=tmp_path,
        output="out_seam.mp4",
        smart_splice=True,
        splice_plan=plan,
        fps=24,
        frames=29,
        seam_interp=True,
        seam_interp_frames=3,
        loudnorm=False,
    )
    assert result["seamInterpApplied"] is True
    assert result["timelineMap"][1]["transitionBeforeFrames"] >= 3
    assert (
        result["timelineMap"][1]["outputStartFrame"]
        == result["timelineMap"][0]["outputEndFrame"]
        + result["timelineMap"][1]["transitionBeforeFrames"]
    )
    out = Path(result["path"])
    assert out.exists()
    probe = probe_media(out)
    assert probe["duration"] > 0.5


def test_smart_splice_seam_interp_falls_back_when_unavailable(monkeypatch, silent_clips, tmp_path: Path):
    monkeypatch.setattr(
        "app.services.concat_video.generate_seam_transition",
        lambda *a, **k: False,
    )
    plan = analyze_splice([str(p) for p in silent_clips], fps=24, max_frames=6)
    result = concat_videos(
        [p.name for p in silent_clips],
        input_dir=tmp_path,
        output="out_seam_fallback.mp4",
        smart_splice=True,
        splice_plan=plan,
        fps=24,
        frames=29,
        seam_interp=True,
        loudnorm=False,
    )
    assert result["seamInterpApplied"] is False
    assert Path(result["path"]).exists()
