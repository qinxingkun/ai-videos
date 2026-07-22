"""媒体管线集成测试：用 ffmpeg 合成短视频验证 probe / concat / extract / validate。"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.services.concat_video import concat_videos
from app.services.media_ops import extract_frame_ffmpeg
from app.services.media_probe import has_audio_stream, probe_media, validate_segment
from app.services.splice_analysis import analyze_splice


def _make_clip(path: Path, *, color: str, seconds: float = 1.0, with_audio: bool = True) -> None:
    args = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c={color}:s=768x512:d={seconds}:r=24",
    ]
    if with_audio:
        args += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}"]
        args += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)]
    else:
        args += ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)]
    r = subprocess.run(args, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-400:]


@pytest.fixture()
def sample_clips(tmp_path: Path):
    clips = []
    for i, color in enumerate(["red", "green", "blue"]):
        p = tmp_path / f"seg{i}.mp4"
        _make_clip(p, color=color, seconds=1.2)
        clips.append(p)
    return clips


def test_probe_and_audio(sample_clips):
    probe = probe_media(sample_clips[0])
    assert probe["width"] == 768
    assert probe["height"] == 512
    assert 1.0 <= probe["duration"] <= 1.5
    assert has_audio_stream(sample_clips[0])


def test_validate_segment(sample_clips):
    result = validate_segment(
        sample_clips[0],
        width=768,
        height=512,
        min_dur=0.5,
        max_dur=2.0,
        require_audio=True,
    )
    assert result["ok"], result


def test_extract_last_frame(sample_clips, tmp_path: Path):
    out = tmp_path / "last.jpg"
    extract_frame_ffmpeg(sample_clips[0], out, position="last")
    assert out.exists() and out.stat().st_size > 100


def test_hard_concat(sample_clips, tmp_path: Path):
    result = concat_videos(
        [p.name for p in sample_clips],
        input_dir=tmp_path,
        output="out_hard.mp4",
        no_fade=True,
        fps=24,
        frames=29,
    )
    out = Path(result["path"])
    assert out.exists()
    probe = probe_media(out)
    assert probe["duration"] >= 3.0


def test_xfade_concat(sample_clips, tmp_path: Path):
    result = concat_videos(
        [p.name for p in sample_clips],
        input_dir=tmp_path,
        output="out_xfade.mp4",
        fade=0.1,
        fps=24,
        frames=29,
    )
    assert Path(result["path"]).exists()


def test_analyze_splice_runs(sample_clips):
    plan = analyze_splice([str(p) for p in sample_clips], fps=24, max_frames=8)
    assert plan["segmentCount"] == 3
    assert len(plan["joins"]) == 2


def test_smart_splice(sample_clips, tmp_path: Path):
    plan = analyze_splice([str(p) for p in sample_clips], fps=24, max_frames=6)
    result = concat_videos(
        [p.name for p in sample_clips],
        input_dir=tmp_path,
        output="out_smart.mp4",
        smart_splice=True,
        splice_plan=plan,
        fps=24,
        frames=29,
        micro_video_fade_sec=0,
        loudnorm=False,
    )
    assert Path(result["path"]).exists()
