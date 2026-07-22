from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from app.services.media_probe import probe_media
from app.services.splice_analysis import _gray_ssim

DEFAULTS = {
    "ssim_threshold": 0.97,
    "min_frames": 4,
    "sample_fps": 12.0,
    "thumb_size": 32,
}


def _extract_sample_frames(video_path: str, *, sample_fps: float, thumb_size: int, tmp: Path) -> list[list[int]]:
    pattern = str(tmp / "f_%05d.png")
    r = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            video_path,
            "-vf",
            f"fps={sample_fps},scale={thumb_size}:{thumb_size}:flags=bilinear,format=gray",
            pattern,
        ],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise RuntimeError((r.stderr or "ffmpeg sample extract failed")[-300:])

    frames: list[list[int]] = []
    for png in sorted(tmp.glob("f_*.png")):
        raw_path = tmp / (png.stem + ".raw")
        c = subprocess.run(
            ["ffmpeg", "-y", "-i", str(png), "-f", "rawvideo", "-pix_fmt", "gray", str(raw_path)],
            capture_output=True,
            text=True,
        )
        if c.returncode != 0:
            continue
        data = raw_path.read_bytes()
        frames.append(list(data[: thumb_size * thumb_size]))
    return frames


def detect_duplicate_frames(video_path: str | Path, **opts: Any) -> dict[str, Any]:
    merged = {**DEFAULTS}
    if opts.get("ssimThreshold") is not None:
        merged["ssim_threshold"] = float(opts["ssimThreshold"])
    if opts.get("ssim_threshold") is not None:
        merged["ssim_threshold"] = float(opts["ssim_threshold"])
    if opts.get("minFrames") is not None:
        merged["min_frames"] = int(opts["minFrames"])
    if opts.get("min_frames") is not None:
        merged["min_frames"] = int(opts["min_frames"])
    if opts.get("sampleFps") is not None:
        merged["sample_fps"] = float(opts["sampleFps"])
    if opts.get("sample_fps") is not None:
        merged["sample_fps"] = float(opts["sample_fps"])

    path = Path(video_path)
    if not path.exists():
        return {"ok": False, "issues": [f"file not found: {path}"], "maxRun": 0, "runs": []}

    try:
        probe = probe_media(path)
    except Exception as e:
        return {"ok": False, "issues": [str(e)], "maxRun": 0, "runs": []}

    tmp = Path(tempfile.mkdtemp(prefix="dupscan-"))
    try:
        frames = _extract_sample_frames(
            str(path),
            sample_fps=merged["sample_fps"],
            thumb_size=merged["thumb_size"],
            tmp=tmp,
        )
        if len(frames) < 2:
            return {"ok": False, "issues": ["too few sample frames"], "maxRun": 0, "runs": [], "probe": probe}

        runs: list[dict] = []
        run_start = None
        run_len = 0
        max_run = 0
        for i in range(1, len(frames)):
            ssim = _gray_ssim(frames[i - 1], frames[i])
            if ssim >= merged["ssim_threshold"]:
                if run_start is None:
                    run_start = i - 1
                run_len += 1
                max_run = max(max_run, run_len + 1)
            else:
                if run_len + 1 >= merged["min_frames"]:
                    runs.append(
                        {
                            "startSample": run_start,
                            "endSample": run_start + run_len,
                            "frames": run_len + 1,
                            "approxSec": round((run_len + 1) / merged["sample_fps"], 3),
                        }
                    )
                run_start = None
                run_len = 0
        if run_len + 1 >= merged["min_frames"]:
            runs.append(
                {
                    "startSample": run_start,
                    "endSample": run_start + run_len,
                    "frames": run_len + 1,
                    "approxSec": round((run_len + 1) / merged["sample_fps"], 3),
                }
            )

        issues: list[str] = []
        if runs:
            issues.append(
                f"{len(runs)} duplicate stretch(es), max {max_run} consecutive near-identical frames "
                f"(ssim≥{merged['ssim_threshold']})"
            )
        return {
            "ok": len(issues) == 0,
            "issues": issues,
            "maxRun": max_run,
            "runs": runs,
            "sampleCount": len(frames),
            "sampleFps": merged["sample_fps"],
            "probe": probe,
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
