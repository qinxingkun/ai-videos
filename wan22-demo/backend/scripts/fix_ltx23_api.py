#!/usr/bin/env python3
"""
从 blueprint 生成 LTX 2.3 T2V/I2V workflow。

  python backend/scripts/fix_ltx23_api.py --from-blueprint --mode t2v
  python backend/scripts/fix_ltx23_api.py --from-blueprint --mode i2v
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT / "scripts"))

from blueprint_to_api import convert  # noqa: E402

DEFAULTS = {
    4: "ltx-2.3-22b-dev-fp8.safetensors",
    5: "ltx_2.3_22b_distilled_1.1_lora_dynamic_fro09_avg_rank_111_bf16.safetensors",
    6: "gemma_3_12B_it_fp4_mixed.safetensors",
    7: "ltx-2.3-spatial-upscaler-x2-1.1.safetensors",
}


def write_workflow(name: str, api: dict) -> None:
    body = json.dumps(api, indent=2, ensure_ascii=False) + "\n"
    for target in (PROJECT_ROOT / "frontend/src/workflows" / name, BACKEND_ROOT / "workflows" / name):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        print(f"Wrote {target} ({len(api)} nodes)")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--from-blueprint", action="store_true")
    p.add_argument("--mode", choices=["t2v", "i2v"], default="t2v")
    args = p.parse_args()

    # 若已有成品 workflow，优先复制同步两端；有 blueprint 再从源生成
    existing = BACKEND_ROOT / "workflows" / f"ltx23_{args.mode}.api.json"
    bp = PROJECT_ROOT.parent / "ComfyUI" / "blueprints" / "Text to Video (LTX-2.3).json"

    if args.from_blueprint and bp.exists():
        blueprint = json.loads(bp.read_text(encoding="utf-8"))
        api = convert(blueprint, "Text to Video (LTX-2.3)")
        # 轻量修补：写入默认模型名（完整修补逻辑保留在已提交的 JSON；此处保证可再生成骨架）
        for node in api.values():
            inputs = node.get("inputs") or {}
            if "ckpt_name" in inputs:
                inputs["ckpt_name"] = DEFAULTS[4]
            if "lora_name" in inputs:
                inputs["lora_name"] = DEFAULTS[5]
            if "text_encoder" in inputs or "text_encoder_name" in inputs:
                key = "text_encoder" if "text_encoder" in inputs else "text_encoder_name"
                inputs[key] = DEFAULTS[6]
        write_workflow(f"ltx23_{args.mode}.api.json", api)
        print("Note: prefer committed patched workflows; re-check node wiring after blueprint regen.")
        return 0

    if existing.exists():
        api = json.loads(existing.read_text(encoding="utf-8"))
        write_workflow(f"ltx23_{args.mode}.api.json", api)
        return 0

    print(f"No blueprint at {bp} and no existing {existing}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
