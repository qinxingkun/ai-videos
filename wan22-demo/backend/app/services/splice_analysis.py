from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from app.services.media_probe import probe_media

DEFAULTS = {
    "fps": 24.0,
    "tail_sec": 1.0,
    "head_sec": 1.0,
    "head_max_sec": 1.5,
    "max_frames": 48,
    "similarity_threshold": 0.9,
    "thumb_size": 64,
    # 运动感知接缝选点：在名义裁切帧 ± motion_search_window 帧内寻找运动最小点
    "motion_search_window": 3,
}


def _extract_thumb(path: str, *, position: str, offset_sec: float, out_path: Path, size: int) -> None:
    probe = probe_media(path)
    args = ["ffmpeg", "-y"]
    if position == "last":
        ss = max(0.0, probe["duration"] - max(0.04, offset_sec))
        args += ["-ss", f"{ss:.4f}", "-i", path]
    else:
        args += ["-ss", str(max(0.0, offset_sec)), "-i", path]
    args += [
        "-frames:v",
        "1",
        "-vf",
        f"scale={size}:{size}:flags=bilinear,format=gray",
        "-f",
        "rawvideo",
        str(out_path),
    ]
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
        raise RuntimeError((r.stderr or "thumb extract failed")[-200:])


def _read_gray(raw_path: Path, size: int) -> list[int]:
    data = raw_path.read_bytes()
    expected = size * size
    if len(data) < expected:
        raise RuntimeError(f"thumb too small: {len(data)} < {expected}")
    return list(data[:expected])


def _phash_from_gray(pixels: list[int], size: int) -> int:
    step = max(1, size // 16)
    samples: list[int] = []
    for y in range(16):
        for x in range(16):
            sy = min(size - 1, y * step)
            sx = min(size - 1, x * step)
            samples.append(pixels[sy * size + sx])
    avg = sum(samples) / len(samples)
    h = 0
    for i, v in enumerate(samples[:64]):
        if v >= avg:
            h |= 1 << i
    return h


def _hash_similarity(a: int, b: int) -> float:
    xor = a ^ b
    diff = bin(xor).count("1")
    return 1 - diff / 64


def _gray_ssim(a: list[int], b: list[int]) -> float:
    n = len(a)
    sum_a = sum_b = sum_aa = sum_bb = sum_ab = 0.0
    for x, y in zip(a, b):
        sum_a += x
        sum_b += y
        sum_aa += x * x
        sum_bb += y * y
        sum_ab += x * y
    mean_a = sum_a / n
    mean_b = sum_b / n
    var_a = sum_aa / n - mean_a * mean_a
    var_b = sum_bb / n - mean_b * mean_b
    cov = sum_ab / n - mean_a * mean_b
    c1 = 6.5025
    c2 = 58.5225
    num = (2 * mean_a * mean_b + c1) * (2 * cov + c2)
    den = (mean_a * mean_a + mean_b * mean_b + c1) * (var_a + var_b + c2)
    return num / den if den > 0 else 0.0


def _motion_scores_near(
    path: str, *, position: str, center_frame: int, fps: float, size: int, window: int, max_offset_sec: float
) -> dict[int, float]:
    """在 center_frame ± window 帧内采样，计算相邻帧运动幅度（1 - SSIM）。

    分数越低代表该处画面越"静"，是更干净的裁切点；用于在既有相似度检测出的
    名义裁切帧附近做微调，而不是死板地按固定秒数裁切。
    """
    tmp = Path(tempfile.mkdtemp(prefix="motion-"))
    scores: dict[int, float] = {}
    try:
        lo = max(0, center_frame - window)
        hi = center_frame + window
        prev_px: list[int] | None = None
        prev_k: int | None = None
        for k in range(lo, hi + 1):
            offset = k / fps
            if offset >= max_offset_sec:
                break
            thumb = tmp / f"m_{k}.raw"
            try:
                _extract_thumb(path, position=position, offset_sec=offset, out_path=thumb, size=size)
            except Exception:
                continue
            px = _read_gray(thumb, size)
            if prev_px is not None and prev_k is not None and prev_k == k - 1:
                scores[k] = round(1 - _gray_ssim(prev_px, px), 4)
            prev_px, prev_k = px, k
        return scores
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _refine_cut_frame(scores: dict[int, float], fallback_frame: int) -> tuple[int, float]:
    if not scores:
        return fallback_frame, 0.0
    best_k = min(scores, key=scores.get)
    return best_k, scores[best_k]


def _analyze_join(left_path: str, right_path: str, opts: dict[str, Any]) -> dict[str, Any]:
    left_probe = probe_media(left_path)
    right_probe = probe_media(right_path)
    fps = opts["fps"] or left_probe["fps"] or 24
    max_frames = opts["max_frames"]
    size = opts["thumb_size"]
    tmp = Path(tempfile.mkdtemp(prefix="splice-"))
    try:
        best_overlap = 0
        best_score = 0.0
        for k in range(1, max_frames + 1):
            left_off = k / fps
            right_off = (k - 1) / fps
            if left_off >= left_probe["duration"] * 0.45:
                break
            if right_off >= right_probe["duration"] * 0.45:
                break
            left_thumb = tmp / f"l_{k}.raw"
            right_thumb = tmp / f"r_{k}.raw"
            _extract_thumb(left_path, position="last", offset_sec=left_off, out_path=left_thumb, size=size)
            _extract_thumb(right_path, position="first", offset_sec=right_off, out_path=right_thumb, size=size)
            left_px = _read_gray(left_thumb, size)
            right_px = _read_gray(right_thumb, size)
            ph_sim = _hash_similarity(_phash_from_gray(left_px, size), _phash_from_gray(right_px, size))
            ssim = _gray_ssim(left_px, right_px)
            score = 0.35 * ph_sim + 0.65 * ssim
            if score >= opts["similarity_threshold"] and score >= best_score:
                best_overlap = k
                best_score = score

        detected_tail = best_overlap / fps
        detected_head = best_overlap / fps
        tail_cut = min(
            left_probe["duration"] * 0.4,
            max(opts["tail_sec"], detected_tail or opts["tail_sec"]),
        )
        head_cut = min(
            right_probe["duration"] * 0.4,
            max(opts["head_sec"], detected_head or opts["head_sec"], tail_cut * 0.9),
        )
        head_cut_capped = min(head_cut, opts["head_max_sec"])

        # 运动感知微调：在名义裁切帧附近找运动最小点，减少可感知跳切
        window = int(opts.get("motion_search_window") or 0)
        tail_frame = round(tail_cut * fps)
        head_frame = round(head_cut_capped * fps)
        seam_motion_score = 0.0
        if window > 0:
            tail_scores = _motion_scores_near(
                left_path,
                position="last",
                center_frame=tail_frame,
                fps=fps,
                size=size,
                window=window,
                max_offset_sec=left_probe["duration"] * 0.45,
            )
            head_scores = _motion_scores_near(
                right_path,
                position="first",
                center_frame=head_frame,
                fps=fps,
                size=size,
                window=window,
                max_offset_sec=right_probe["duration"] * 0.45,
            )
            refined_tail_frame, tail_motion = _refine_cut_frame(tail_scores, tail_frame)
            refined_head_frame, head_motion = _refine_cut_frame(head_scores, head_frame)
            # 微调幅度限制在搜索窗口内，且不低于用户设定的最小裁切秒数
            tail_cut = max(opts["tail_sec"], min(left_probe["duration"] * 0.4, refined_tail_frame / fps))
            head_cut_capped = max(
                min(opts["head_sec"], opts["head_max_sec"]),
                min(right_probe["duration"] * 0.4, opts["head_max_sec"], refined_head_frame / fps),
            )
            seam_motion_score = round((tail_motion + head_motion) / 2, 4)

        return {
            "joinIndex": None,
            "tailCutSec": round(tail_cut, 4),
            "headCutSec": round(head_cut_capped, 4),
            "overlapFrames": best_overlap,
            "confidence": round(best_score, 4),
            "leftDuration": round(left_probe["duration"], 4),
            "rightDuration": round(right_probe["duration"], 4),
            "seamMotionScore": seam_motion_score,
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def analyze_splice(paths: list[str], **opts: Any) -> dict[str, Any]:
    merged = {**DEFAULTS}
    for key in (
        "fps",
        "tail_sec",
        "head_sec",
        "head_max_sec",
        "max_frames",
        "similarity_threshold",
        "thumb_size",
        "motion_search_window",
    ):
        if opts.get(key) is not None:
            merged[key] = opts[key]
    # accept camelCase from API
    if opts.get("tailSec") is not None:
        merged["tail_sec"] = opts["tailSec"]
    if opts.get("headSec") is not None:
        merged["head_sec"] = opts["headSec"]
    if opts.get("headMaxSec") is not None:
        merged["head_max_sec"] = opts["headMaxSec"]
    if opts.get("fps") is not None:
        merged["fps"] = float(opts["fps"])
    if opts.get("maxFrames") is not None:
        merged["max_frames"] = int(opts["maxFrames"])
    if opts.get("motionSearchWindow") is not None:
        merged["motion_search_window"] = int(opts["motionSearchWindow"])

    joins = []
    for i in range(len(paths) - 1):
        join = _analyze_join(paths[i], paths[i + 1], merged)
        join["joinIndex"] = i
        joins.append(join)
    return {"joins": joins, "segmentCount": len(paths), "fps": merged["fps"]}
