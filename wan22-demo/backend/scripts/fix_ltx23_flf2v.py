#!/usr/bin/env python3
"""同步 / 生成 LTX FLF2V workflow 到 frontend + backend。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT / "scripts"))

from blueprint_to_api import convert  # noqa: E402


def main() -> int:
    name = "ltx23_flf2v.api.json"
    existing = BACKEND_ROOT / "workflows" / name
    bp = PROJECT_ROOT.parent / "ComfyUI" / "blueprints" / "First-Last-Frame to Video (LTX-2.3).json"
    if bp.exists():
        blueprint = json.loads(bp.read_text(encoding="utf-8"))
        try:
            api = convert(blueprint, "First-Last-Frame to Video (LTX-2.3)")
        except Exception:
            api = json.loads(existing.read_text(encoding="utf-8")) if existing.exists() else None
            if not api:
                raise
    elif existing.exists():
        api = json.loads(existing.read_text(encoding="utf-8"))
    else:
        print("No FLF2V blueprint or existing workflow", file=sys.stderr)
        return 1

    body = json.dumps(api, indent=2, ensure_ascii=False) + "\n"
    for target in (PROJECT_ROOT / "frontend/src/workflows" / name, BACKEND_ROOT / "workflows" / name):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        print(f"Wrote {target} ({len(api)} nodes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
