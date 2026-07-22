#!/usr/bin/env python3
"""成片重复帧扫描 CLI。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.duplicate_frames import detect_duplicate_frames  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--ssim-threshold", type=float, default=0.97)
    p.add_argument("--min-frames", type=int, default=4)
    p.add_argument("--sample-fps", type=float, default=12)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    result = detect_duplicate_frames(
        Path(args.input).resolve(),
        ssim_threshold=args.ssim_threshold,
        min_frames=args.min_frames,
        sample_fps=args.sample_fps,
    )
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("OK: no duplicate stretches" if result["ok"] else f"FAIL: {'; '.join(result['issues'])}")
        for r in result.get("runs") or []:
            print(f"  samples {r['startSample']}-{r['endSample']}: {r['frames']} frames (~{r['approxSec']}s)")
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
