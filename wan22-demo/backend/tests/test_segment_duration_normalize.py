"""单段时长规范与 duration-only 质检诊断。"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.services.media_probe import (
    is_duration_only_failure,
    normalize_segment_duration,
    probe_media,
    validate_segment,
)


def _make_clip(path: Path, *, seconds: float, fps: float = 16, size: str = "1280x720") -> None:
    args = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=blue:s={size}:d={seconds}:r={fps}",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(path),
    ]
    r = subprocess.run(args, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-400:]


def test_is_duration_only_failure():
    assert is_duration_only_failure(["duration 9.56s > 6.0s"])
    assert is_duration_only_failure(
        ["duration 9.56s > 6.0s（≈153 frames @ 16.00fps；expected 81@16）"]
    )
    assert not is_duration_only_failure(["duration 9.56s > 6.0s", "width 640 != 1280"])
    assert not is_duration_only_failure([])


def test_validate_segment_duration_issue_includes_frames_fps(tmp_path: Path):
    clip = tmp_path / "long.mp4"
    _make_clip(clip, seconds=9.56, fps=16)
    result = validate_segment(
        clip,
        width=1280,
        height=720,
        min_dur=4.5,
        max_dur=6.0,
        expected_frames=81,
        expected_fps=16,
    )
    assert result["ok"] is False
    assert result["durationOnly"] is True
    assert any("duration" in issue and "expected 81@16" in issue for issue in result["issues"])
    assert result["nbFrames"] is not None


def test_normalize_segment_duration_trims_overlong_clip(tmp_path: Path):
    source = tmp_path / "overlong.mp4"
    output = tmp_path / "normalized.mp4"
    _make_clip(source, seconds=9.56, fps=16)
    before = probe_media(source)
    assert before["duration"] > 6.0

    result = normalize_segment_duration(
        source,
        output,
        expected_frames=81,
        fps=16,
        max_duration=6.0,
    )
    assert result["applied"] is True
    assert Path(result["path"]).is_file()
    after = probe_media(output)
    assert after["duration"] <= 6.0
    assert after["duration"] == pytest.approx(81 / 16, abs=0.15)

    skipped = normalize_segment_duration(
        output,
        tmp_path / "again.mp4",
        expected_frames=81,
        fps=16,
        max_duration=6.0,
    )
    assert skipped["applied"] is False
