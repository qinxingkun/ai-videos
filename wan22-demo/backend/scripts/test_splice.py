#!/usr/bin/env python3
"""Smart Splice 回归：analyze + concat 流水线（需样例视频）。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.concat_video import concat_videos  # noqa: E402
from app.services.media_probe import has_audio_stream, probe_media  # noqa: E402
from app.services.splice_analysis import analyze_splice  # noqa: E402

PROJECT_ROOT = BACKEND_ROOT.parent
VIDEO_DIR = Path(os.environ.get("COMFYUI_VIDEO_DIR") or PROJECT_ROOT.parent / "ComfyUI" / "output" / "video")
SAMPLES = [
    "ltx-2.3-22b-dev-fp8-20260707-1557_00001_.mp4",
    "ltx-2.3-22b-dev-fp8-chain_last_01-20260707-1557_00001_.mp4",
    "ltx-2.3-22b-dev-fp8-chain_last_02-20260707-1558_00001_.mp4",
    "ltx-2.3-22b-dev-fp8-chain_last_03-20260707-1558_00001_.mp4",
    "ltx-2.3-22b-dev-fp8-chain_last_04-20260707-1559_00001_.mp4",
    "ltx-2.3-22b-dev-fp8-chain_last_05-20260707-1559_00001_.mp4",
]


def main() -> int:
    paths = [VIDEO_DIR / f for f in SAMPLES]
    missing = [p for p in paths if not p.exists()]
    if missing:
        print(f"SKIP: missing {len(missing)} sample videos under {VIDEO_DIR}")
        return 0

    plan = analyze_splice([str(p) for p in paths], fps=24)
    assert len(plan["joins"]) == 5, plan
    print(f"OK analyze-splice joins={len(plan['joins'])}")

    out = concat_videos(
        SAMPLES,
        input_dir=VIDEO_DIR,
        output="_test_splice_final.mp4",
        smart_splice=True,
        fps=24,
        frames=121,
        splice_plan=plan,
    )
    probe = probe_media(out["path"])
    assert probe["width"] == 768 and probe["height"] == 512, probe
    assert 15 <= probe["duration"] <= 25, probe
    assert has_audio_stream(out["path"])
    print(f"OK concat → {out['path']} {probe['duration']:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
