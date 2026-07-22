#!/usr/bin/env python3
"""多分镜视频拼接 CLI。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.concat_video import concat_videos  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Concat video segments with ffmpeg")
    p.add_argument("--files", required=True, help="comma-separated mp4 list")
    p.add_argument("--input-dir", default=".")
    p.add_argument("--output", default="final_30s_xfade.mp4")
    p.add_argument("--fps", type=float, default=24)
    p.add_argument("--frames", type=int, default=121)
    p.add_argument("--fade", type=float, default=0.2)
    p.add_argument("--no-fade", action="store_true")
    p.add_argument("--chain-trim", action="store_true")
    p.add_argument("--smart-splice", action="store_true")
    p.add_argument("--splice-plan")
    p.add_argument("--trim-head-frames", type=int, default=24)
    p.add_argument("--trim-tail-frames", type=int, default=24)
    p.add_argument("--head-sec", type=float, default=1.0)
    p.add_argument("--tail-sec", type=float, default=1.0)
    p.add_argument("--audio-crossfade", type=float, default=0.05)
    p.add_argument("--micro-fade", type=float, default=2 / 24)
    p.add_argument("--output-width", type=int, default=768)
    p.add_argument("--output-height", type=int, default=512)
    args = p.parse_args()

    files = [s.strip() for s in args.files.split(",") if s.strip()]
    plan = None
    if args.splice_plan:
        plan = json.loads(Path(args.splice_plan).read_text(encoding="utf-8"))

    result = concat_videos(
        files,
        input_dir=args.input_dir,
        output=args.output,
        fps=args.fps,
        frames=args.frames,
        fade=args.fade,
        no_fade=args.no_fade,
        chain_trim=args.chain_trim or args.smart_splice,
        smart_splice=args.smart_splice,
        splice_plan=plan,
        trim_head_frames=args.trim_head_frames,
        trim_tail_frames=args.trim_tail_frames,
        head_sec=args.head_sec,
        tail_sec=args.tail_sec,
        audio_crossfade_sec=args.audio_crossfade,
        micro_video_fade_sec=args.micro_fade,
        output_width=args.output_width,
        output_height=args.output_height,
    )
    print(f"Wrote {result['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
