from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from app.services.media_probe import probe_media

DEFAULTS = {
    "threshold": 0.32,
    "max_frames": 5,
}

# 与 README / 前端约定一致；validate_segment 默认阈值
DEFAULT_IDENTITY_THRESHOLD = DEFAULTS["threshold"]

_APP: Any = None
_APP_LOAD_ERROR: str | None = None


def _get_app() -> Any:
    """惰性加载 insightface FaceAnalysis（buffalo_l/ArcFace，纯推理，CPU 即可）。

    与生成显存无关；若依赖未安装/加载失败，返回 None，调用方需优雅降级（skip 而非报错中止）。
    """
    global _APP, _APP_LOAD_ERROR
    if _APP is not None or _APP_LOAD_ERROR is not None:
        return _APP
    try:
        from insightface.app import FaceAnalysis  # noqa: PLC0415
        from app.config import get_settings  # noqa: PLC0415

        app = FaceAnalysis(
            name="buffalo_l",
            root=str(get_settings().insightface_root),
            providers=["CPUExecutionProvider"],
        )
        app.prepare(ctx_id=-1, det_size=(320, 320))
        _APP = app
    except Exception as e:  # pragma: no cover - 依赖缺失时的降级路径
        _APP_LOAD_ERROR = str(e)
        _APP = None
    return _APP


def is_available() -> bool:
    return _get_app() is not None


def unavailable_reason() -> str | None:
    _get_app()
    return _APP_LOAD_ERROR


def _extract_sample_frames(path: Path, *, max_frames: int, out_dir: Path) -> list[Path]:
    """均匀采样若干帧（跳过首尾各 10%，避开链式衔接处易糊的边界帧）。"""
    probe = probe_media(path)
    duration = max(0.2, float(probe.get("duration") or 0.2))
    n = max(1, max_frames)
    frames: list[Path] = []
    for i in range(n):
        t = duration * (0.1 + 0.8 * i / max(1, n - 1)) if n > 1 else duration * 0.5
        out_path = out_dir / f"f_{i}.jpg"
        r = subprocess.run(
            ["ffmpeg", "-y", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1", "-q:v", "2", str(out_path)],
            capture_output=True,
            text=True,
        )
        if r.returncode == 0 and out_path.exists():
            frames.append(out_path)
    return frames


def _biggest_face_embedding(app: Any, image_path: Path):
    import cv2  # noqa: PLC0415

    img = cv2.imread(str(image_path))
    if img is None:
        return None
    faces = app.get(img)
    if not faces:
        return None
    best = max(faces, key=lambda f: max(0.0, f.bbox[2] - f.bbox[0]) * max(0.0, f.bbox[3] - f.bbox[1]))
    emb = getattr(best, "normed_embedding", None)
    return emb


def detect_face_in_image(image_path: str | Path) -> dict[str, Any]:
    """单图人脸门控：末帧无人脸时链式条件应回退定妆照。

    依赖缺失时 skipped=True（调用方可保守回退定妆照，或忽略门控）。
    """
    path = Path(image_path)
    if not path.exists():
        return {
            "ok": False,
            "hasFace": False,
            "skipped": True,
            "reason": f"图片不存在: {path}",
            "faceCount": 0,
        }
    app = _get_app()
    if app is None:
        return {
            "ok": True,
            "hasFace": None,
            "skipped": True,
            "reason": _APP_LOAD_ERROR or "insightface 未安装，跳过人脸门控",
            "faceCount": 0,
        }
    import cv2  # noqa: PLC0415

    img = cv2.imread(str(path))
    if img is None:
        return {
            "ok": False,
            "hasFace": False,
            "skipped": False,
            "reason": "无法读取图片",
            "faceCount": 0,
        }
    faces = app.get(img) or []
    count = len(faces)
    return {
        "ok": True,
        "hasFace": count > 0,
        "skipped": False,
        "faceCount": count,
        "reason": None if count > 0 else "未检测到人脸",
    }


def _cosine(a, b) -> float:
    import numpy as np  # noqa: PLC0415

    a = np.asarray(a, dtype="float64")
    b = np.asarray(b, dtype="float64")
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def check_identity_similarity(
    video_path: str | Path,
    reference_image_path: str | Path,
    *,
    threshold: float | None = None,
    max_frames: int | None = None,
) -> dict[str, Any]:
    """人脸一致性质检：候选视频采样帧与参考定妆照的 ArcFace cosine 相似度。

    与 duplicate_frames.py 同等定位：纯 Python 质检模块，复用 ffmpeg 抽帧基础设施。
    依赖缺失/参考图缺失/未检测到人脸时返回 ok=True, skipped=True（不阻断现有生成流程），
    由调用方决定是否将 skipped 结果计入自愈重试判断。
    """
    thr = threshold if threshold is not None else DEFAULTS["threshold"]
    frames_n = max_frames if max_frames is not None else DEFAULTS["max_frames"]

    ref_path = Path(reference_image_path)
    if not reference_image_path or not ref_path.exists():
        return {
            "ok": True,
            "skipped": True,
            "reason": f"参考定妆照不存在: {ref_path}",
            "avgSimilarity": None,
            "minSimilarity": None,
            "issues": [],
        }
    app = _get_app()
    if app is None:
        return {
            "ok": True,
            "skipped": True,
            "reason": _APP_LOAD_ERROR or "insightface 未安装，跳过人脸一致性质检",
            "avgSimilarity": None,
            "minSimilarity": None,
            "issues": [],
        }

    ref_emb = _biggest_face_embedding(app, ref_path)
    if ref_emb is None:
        return {
            "ok": True,
            "skipped": True,
            "reason": "参考定妆照未检测到人脸",
            "avgSimilarity": None,
            "minSimilarity": None,
            "issues": [],
        }

    tmp = Path(tempfile.mkdtemp(prefix="idqa-"))
    try:
        frames = _extract_sample_frames(Path(video_path), max_frames=frames_n, out_dir=tmp)
        sims: list[float] = []
        for f in frames:
            emb = _biggest_face_embedding(app, f)
            if emb is not None:
                sims.append(_cosine(ref_emb, emb))
        if not sims:
            return {
                "ok": False,
                "skipped": False,
                "avgSimilarity": 0.0,
                "minSimilarity": 0.0,
                "sampledFrames": len(frames),
                "facesDetected": 0,
                "issues": ["候选视频采样帧未检测到人脸"],
            }
        avg = sum(sims) / len(sims)
        mn = min(sims)
        issues: list[str] = []
        if avg < thr:
            issues.append(f"人脸相似度均值 {avg:.3f} < 阈值 {thr}")
        return {
            "ok": len(issues) == 0,
            "skipped": False,
            "avgSimilarity": round(avg, 4),
            "minSimilarity": round(mn, 4),
            "sampledFrames": len(frames),
            "facesDetected": len(sims),
            "threshold": thr,
            "issues": issues,
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
