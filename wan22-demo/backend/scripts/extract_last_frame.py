#!/usr/bin/env python3
"""从 mp4 抽取末帧为 jpg。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.media_ops import extract_frame_ffmpeg  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    in_path = Path(args.input).resolve()
    out_path = Path(args.output).resolve()
    if not in_path.exists():
        print(f"Input not found: {in_path}", file=sys.stderr)
        return 1
    out_path.parent.mkdir(parents=True, exist_ok=True)
    extract_frame_ffmpeg(in_path, out_path, position="last", offset_before_end=0.05)
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
