#!/usr/bin/env python3
"""校验双人对话 T2V 测试用例 prompt。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.dialogue_prompt import build_shot_prompt_with_dialogue, build_speech_block  # noqa: E402

FIXTURE = BACKEND_ROOT / "data" / "fixtures" / "ltx_t2v_two_person_dialogue.json"


def main() -> int:
    test = json.loads(FIXTURE.read_text(encoding="utf-8"))
    failed = 0
    print(f"\n=== {test['title']} ({test['id']}) ===\n")
    print(test["description"])
    print("角色:", " + ".join(c["name"] for c in test["characters"]), "\n")

    for i, shot in enumerate(test["shots"]):
        prompt = build_shot_prompt_with_dialogue(
            shot_prompt=shot["prompt"],
            dialogue_text=shot["dialogue"],
            characters=test["characters"],
            style_suffix=test["styleSuffix"],
            dialogue_mode=test["dialogueMode"],
            engine=test["engine"],
            segment_index=i,
            all_shots=test["shots"],
            scene_bible=test.get("sceneBible", ""),
            chained=i > 0,
        )
        checks = [
            ("Style", "style:" in prompt.lower()),
            ("Characters", "characters in scene" in prompt.lower()),
            ("Setting", "setting:" in prompt.lower()),
            ("Ambient", "ambient sound" in prompt.lower()),
            ("speaks", "speaks" in prompt.lower() or "replies" in prompt.lower()),
            ("Mandarin", "mandarin" in prompt.lower()),
        ]
        if i > 0:
            checks.append(("Continuity", "continuity:" in prompt.lower()))

        speech = build_speech_block(shot["dialogue"], test["characters"])
        ok = all(c[1] for c in checks) and bool(speech)
        status = "✓" if ok else "✗"
        print(f"{status} 段 {i + 1} {shot['name']}")
        print(f"  台词: {shot['dialogue'].replace(chr(10), ' | ')}")
        print(f"  prompt 预览: {prompt[:120]}…")
        if not ok:
            failed += 1
            missing = [n for n, v in checks if not v]
            print(f"  缺少: {missing}")

    if failed:
        print(f"\n失败 {failed} 段")
        return 1
    print("\n全部 6 段 prompt 校验通过。\n")
    print("下一步: python backend/scripts/submit_dialogue_test_shot.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
