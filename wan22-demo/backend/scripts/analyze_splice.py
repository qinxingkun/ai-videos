#!/usr/bin/env python3
"""段间重叠分析 CLI。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.splice_analysis import analyze_splice  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--files", required=True)
    p.add_argument("--input-dir", default=".")
    p.add_argument("--fps", type=float, default=24)
    p.add_argument("--tail-sec", type=float, default=1.0)
    p.add_argument("--head-sec", type=float, default=1.0)
    p.add_argument("--head-max-sec", type=float, default=1.5)
    p.add_argument("--output")
    args = p.parse_args()

    input_dir = Path(args.input_dir).resolve()
    files = [s.strip() for s in args.files.split(",") if s.strip()]
    paths = [str(input_dir / f) if not Path(f).is_absolute() else f for f in files]
    plan = analyze_splice(
        paths,
        fps=args.fps,
        tailSec=args.tail_sec,
        headSec=args.head_sec,
        headMaxSec=args.head_max_sec,
    )
    text = json.dumps(plan, indent=2, ensure_ascii=False)
    if args.output:
        out = Path(args.output)
        if not out.is_absolute():
            out = input_dir / out
        out.write_text(text + "\n", encoding="utf-8")
        print(f"Wrote {out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
