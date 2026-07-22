#!/usr/bin/env python3
"""提交双人对话测试用例的单段 T2V。"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.dialogue_prompt import build_shot_prompt_with_dialogue  # noqa: E402

FIXTURE = BACKEND_ROOT / "data" / "fixtures" / "ltx_t2v_two_person_dialogue.json"
API = (os.environ.get("API") or os.environ.get("TOOL_API") or "http://127.0.0.1:8190").rstrip("/")
LTX_DIALOGUE_NEG = (
    "blurry, low quality, distorted face, morphing face, duplicate people, "
    "extra limbs, text overlay, watermark, cartoon, anime"
)
LTX_FRAMES_5S = 121
LTX_FPS = 24
LTX_RES = {"width": 768, "height": 512}


def request(path: str, method: str = "GET", body: dict | None = None):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{API}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def wait_for_video(task_id: str, timeout_ms: int = 25 * 60 * 1000):
    start = time.time()
    while (time.time() - start) * 1000 < timeout_ms:
        task = request(f"/v1/videos/tasks/{task_id}")
        if task.get("status") == "completed":
            media = task.get("media") or []
            if not media:
                raise RuntimeError("任务完成但无输出媒体")
            return media[0]
        if task.get("status") == "failed":
            raise RuntimeError(task.get("error") or "视频生成失败")
        elapsed = int(time.time() - start)
        print(f"\r等待生成… {elapsed}s ({task.get('status')})   ", end="", flush=True)
        time.sleep(3)
    raise RuntimeError("等待超时")


def main() -> int:
    shot_num = 1
    if "--shot" in sys.argv:
        shot_num = int(sys.argv[sys.argv.index("--shot") + 1])
    test = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if shot_num < 1 or shot_num > len(test["shots"]):
        print(f"--shot 须为 1–{len(test['shots'])}")
        return 1
    shot = test["shots"][shot_num - 1]

    print(f"\n=== 提交测试用例: {test['title']} ===")
    print(f"API: {API}")
    print(f"段 {shot_num}/{len(test['shots'])}: {shot['name']}")
    print(f"台词: {shot['dialogue'].replace(chr(10), ' | ')}\n")

    try:
        health = request("/health/full")
        if not health.get("ok"):
            failed = [c["name"] for c in (health.get("checks") or []) if not c.get("ok")]
            raise RuntimeError(f"环境预检失败: {', '.join(failed) or 'unknown'}")
    except Exception as e:
        print("无法连接后端，请先启动: cd backend && python main.py")
        print(e)
        return 1

    prompt = build_shot_prompt_with_dialogue(
        shot_prompt=shot["prompt"],
        dialogue_text=shot["dialogue"],
        characters=test["characters"],
        style_suffix=test["styleSuffix"],
        dialogue_mode=test["dialogueMode"],
        engine="ltx",
        segment_index=shot_num - 1,
        all_shots=test["shots"],
        scene_bible=test.get("sceneBible", ""),
        chained=shot_num > 1,
    )
    print("正向 prompt:")
    print(prompt)
    print()

    submitted = request(
        "/v1/videos/t2v",
        method="POST",
        body={
            "prompt": prompt,
            "negative_prompt": LTX_DIALOGUE_NEG,
            "engine": "ltx",
            "width": LTX_RES["width"],
            "height": LTX_RES["height"],
            "length": LTX_FRAMES_5S,
            "seed": test["baseSeed"] + shot_num - 1,
            "fps": LTX_FPS,
            "filename_prefix": f"video/LTX23_test_{shot['name']}",
        },
    )
    print(f"已提交 task_id: {submitted['task_id']}  prompt_id: {submitted['prompt_id']}")
    print("生成中（LTX T2V 单段约 10–20 分钟）…\n")

    media = wait_for_video(submitted["task_id"])
    url = f"{API}{media['url']}" if media.get("url") else media.get("comfy_url")
    print("\n\n完成！")
    print(f"文件: {media.get('subfolder', '')}/{media.get('filename')}")
    print(f"预览: {url}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.URLError as e:
        print("错误:", e)
        raise SystemExit(1)
    except Exception as e:
        print("\n错误:", e)
        raise SystemExit(1)
