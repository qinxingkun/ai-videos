#!/usr/bin/env python3
"""Smoke test for REST API. Run with: python scripts/smoke_api.py [base_url]"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8190").rstrip("/")


def get(path: str):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=10) as r:
        return json.loads(r.read().decode())


def post(path: str, body: dict):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def main() -> int:
    print(f"smoke against {BASE}")
    health = get("/health")
    assert health.get("ok") is True, health
    print("OK /health")

    full = get("/health/full")
    assert full.get("ok") is not None
    print("OK /health/full checks=", len(full.get("checks") or []))

    chars = get("/v1/characters")
    print("OK /v1/characters:", len(chars.get("characters") or []))

    comfy_ok = any(c.get("name") == "comfyui" and c.get("ok") for c in (full.get("checks") or []))
    if comfy_ok:
        print("ComfyUI online — submitting smoke T2V (queued only, no wait)")
        sub = post("/v1/videos/t2v", {"prompt": "smoke test sunset", "engine": "ltx", "length": 121})
        print("OK POST /v1/videos/t2v:", sub.get("task_id"), sub.get("status"))
        task = get(f"/v1/videos/tasks/{sub['task_id']}")
        print("OK GET /v1/videos/tasks/…:", task.get("status"))
    else:
        print("SKIP POST /v1/videos/t2v (ComfyUI offline)")

    print("SMOKE PASSED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.URLError as e:
        print("SMOKE FAILED: server not reachable — start with: python main.py", e)
        raise SystemExit(1)
    except Exception as e:
        print("SMOKE FAILED:", e)
        raise SystemExit(1)
