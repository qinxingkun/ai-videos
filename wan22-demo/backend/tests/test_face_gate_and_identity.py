"""无脸门控 + ArcFace 接入 validate_segment。"""
from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.services import media_ops
from app.services.character_qa import detect_face_in_image


def test_detect_face_missing_image(tmp_path: Path):
    result = detect_face_in_image(tmp_path / "nope.jpg")
    assert result["hasFace"] is False
    assert result["skipped"] is True


def test_detect_face_gate_api(monkeypatch, tmp_path: Path):
    settings = Settings(comfyui_root=tmp_path / "ComfyUI")
    settings.input_dir.mkdir(parents=True)
    img = settings.input_dir / "face.jpg"
    img.write_bytes(b"\x00")

    monkeypatch.setattr(
        "app.services.character_qa.detect_face_in_image",
        lambda _p: {"ok": True, "hasFace": False, "skipped": False, "faceCount": 0, "reason": "未检测到人脸"},
    )
    result = media_ops.detect_face_gate({"imageName": "face.jpg"}, settings=settings)
    assert result["hasFace"] is False
    assert result["imageName"] == "face.jpg"


def test_validate_segment_merges_identity_failure(monkeypatch, tmp_path: Path):
    settings = Settings(comfyui_root=tmp_path / "ComfyUI")
    (settings.comfyui_root / "output" / "video").mkdir(parents=True)
    settings.input_dir.mkdir(parents=True)
    video = settings.video_dir / "seg.mp4"
    video.write_bytes(b"fake")
    ref = settings.input_dir / "hero.png"
    ref.write_bytes(b"\x00")

    monkeypatch.setattr(
        "app.services.media_ops.probe_validate_segment",
        lambda *a, **k: {"ok": True, "issues": [], "duration": 5.0, "width": 1280, "height": 720},
    )
    monkeypatch.setattr(
        "app.services.character_qa.check_identity_similarity",
        lambda *a, **k: {
            "ok": False,
            "skipped": False,
            "avgSimilarity": 0.1,
            "minSimilarity": 0.05,
            "issues": ["人脸相似度均值 0.100 < 阈值 0.32"],
        },
    )
    result = media_ops.validate_segment(
        {"filename": "seg.mp4", "referenceImageName": "hero.png"},
        settings=settings,
    )
    assert result["ok"] is False
    assert result["durationOnly"] is False
    assert result["identity"]["avgSimilarity"] == 0.1
    assert any("人脸相似度" in x for x in result["issues"])
