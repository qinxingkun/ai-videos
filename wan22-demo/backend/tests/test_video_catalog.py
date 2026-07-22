from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from app.services import video_catalog


def test_parse_filename_timestamp():
    ts = video_catalog.parse_filename_timestamp(
        "wan2.2_t2v_high_noise_14B_fp8_scaled-20260717-1441_00001_.mp4"
    )
    assert ts > 0
    from datetime import datetime

    dt = datetime.fromtimestamp(ts / 1000)
    assert dt.year == 2026
    assert dt.month == 7
    assert dt.day == 17
    assert dt.hour == 14
    assert dt.minute == 41


def test_infer_mode_from_filename():
    assert "t2v" in video_catalog.infer_mode_from_filename("wan2.2_t2v_foo.mp4")
    assert "i2v" in video_catalog.infer_mode_from_filename("wan2.2_i2v_foo.mp4")
    assert video_catalog.infer_mode_from_filename("ltx23_t2v_foo.mp4").startswith("ltx")


def test_list_recent_videos_sorts_by_filename_timestamp(tmp_path: Path):
    older = tmp_path / "wan2.2_t2v_foo-20260717-1200_00001_.mp4"
    newer = tmp_path / "wan2.2_t2v_foo-20260717-1430_00001_.mp4"
    older.write_bytes(b"x")
    newer.write_bytes(b"x")
    # Ensure mtime does not override filename ordering
    os.utime(older, (time.time(), time.time()))
    os.utime(newer, (time.time() - 3600, time.time() - 3600))

    result = video_catalog.list_recent_videos(tmp_path, limit=10)
    assert result["totalFiles"] == 2
    assert result["returned"] == 2
    assert result["videos"][0]["filename"] == newer.name
    assert result["videos"][1]["filename"] == older.name
    assert result["videos"][0]["label"] == "ComfyUI 导入"
    assert result["videos"][0]["url"].startswith("/v1/media/view?")


def test_list_recent_videos_respects_limit(tmp_path: Path):
    for hour in range(5):
        name = f"wan2.2_t2v_foo-20260717-{hour:02d}00_00001_.mp4"
        (tmp_path / name).write_bytes(b"x")

    result = video_catalog.list_recent_videos(tmp_path, limit=2)
    assert result["totalFiles"] == 5
    assert result["returned"] == 2


def test_list_recent_videos_empty_dir(tmp_path: Path):
    result = video_catalog.list_recent_videos(tmp_path, limit=5)
    assert result["videos"] == []
    assert result["totalFiles"] == 0
