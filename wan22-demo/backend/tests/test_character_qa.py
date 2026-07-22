"""人脸一致性质检：依赖缺失/参考图缺失时必须优雅降级（skip），不阻断现有生成流程。"""
from __future__ import annotations

from pathlib import Path

from app.services.character_qa import check_identity_similarity


def test_skips_when_reference_missing(tmp_path: Path):
    video = tmp_path / "not_a_real_video.mp4"
    video.write_bytes(b"\x00")
    result = check_identity_similarity(video, tmp_path / "missing_reference.jpg")
    assert result["ok"] is True
    assert result["skipped"] is True
    assert result["issues"] == []


def test_skips_gracefully_when_dependency_unavailable(monkeypatch, tmp_path: Path):
    import app.services.character_qa as qa

    monkeypatch.setattr(qa, "_get_app", lambda: None)
    monkeypatch.setattr(qa, "_APP_LOAD_ERROR", "insightface not installed (test)")
    ref = tmp_path / "ref.jpg"
    ref.write_bytes(b"\x00")
    video = tmp_path / "seg.mp4"
    video.write_bytes(b"\x00")
    result = check_identity_similarity(video, ref)
    assert result["ok"] is True
    assert result["skipped"] is True
