from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.services.comfy_client import ComfyClient
from app.services.task_store import task_store
from app.services.workflow_builder import (
    build_i2v,
    build_ltx23_flf2v,
    build_ltx23_i2v,
    build_ltx23_t2v,
    build_t2v,
    build_vace_i2v,
    build_wan_flf2v,
    extract_media_from_history,
    load_workflow,
)


def _workflow_path(engine: str, mode: str, use_lightx2v: bool = False):
    settings = get_settings()
    d = settings.workflows_dir
    if engine == "ltx":
        mapping = {
            "t2v": d / "ltx23_t2v.api.json",
            "i2v": d / "ltx23_i2v.api.json",
            "flf2v": d / "ltx23_flf2v.api.json",
        }
        return mapping[mode]
    if mode == "t2v":
        return d / ("t2v_lightx2v.api.json" if use_lightx2v else "t2v.api.json")
    if mode == "i2v":
        return d / "i2v.api.json"
    if mode == "vace":
        return d / "vace_i2v.api.json"
    if mode == "flf2v":
        return d / "flf2v.api.json"
    raise ValueError(f"unsupported wan mode: {mode}")


def _map_args(args: dict) -> dict:
    # 不要写入 None：否则 params.get("fps", 24) 会拿到 None 并覆盖默认值
    raw = {
        "positivePrompt": args.get("prompt") or args.get("positivePrompt"),
        "negativePrompt": args.get("negative_prompt") or args.get("negativePrompt") or "",
        "width": args.get("width"),
        "height": args.get("height"),
        "length": args.get("length"),
        "fps": args.get("fps"),
        "seed": args.get("seed"),
        "steps": args.get("steps"),
        "cfg": args.get("cfg"),
        "filenamePrefix": args.get("filename_prefix") or args.get("filenamePrefix"),
        "useLightX2V": args.get("use_lightx2v") or args.get("useLightX2V") or False,
        "imageName": args.get("image_name") or args.get("imageName"),
        "firstImageName": args.get("first_image_name") or args.get("firstImageName"),
        "lastImageName": args.get("last_image_name") or args.get("lastImageName"),
        "i2vStrength": args.get("i2v_strength") if args.get("i2v_strength") is not None else args.get("i2vStrength"),
        "anchorImageName": args.get("anchor_image_name") or args.get("anchorImageName"),
        "anchorBlendWeight": (
            args.get("anchor_blend_weight")
            if args.get("anchor_blend_weight") is not None
            else args.get("anchorBlendWeight")
        ),
        "useVace": args.get("use_vace") or args.get("useVace") or False,
        "refImageName": args.get("ref_image_name") or args.get("refImageName"),
        "vaceStrength": (
            args.get("vace_strength") if args.get("vace_strength") is not None else args.get("vaceStrength")
        ),
    }
    return {k: v for k, v in raw.items() if v is not None}


async def _submit(graph: dict, meta: dict) -> dict:
    async with ComfyClient() as comfy:
        client_id = ComfyClient.create_client_id()
        res = await comfy.queue_prompt(graph, client_id)
        prompt_id = res["prompt_id"]
        task_id = task_store.create(prompt_id, client_id, meta=meta)
        return {
            "task_id": task_id,
            "prompt_id": prompt_id,
            "client_id": client_id,
            "status": "queued",
            "meta": meta,
        }


async def generate_video_t2v(args: dict[str, Any]) -> dict:
    engine = args.get("engine") or "ltx"
    params = _map_args(args)
    path = _workflow_path(engine, "t2v", bool(params.get("useLightX2V")))
    base = load_workflow(path)
    built = build_ltx23_t2v(base, params) if engine == "ltx" else build_t2v(base, params)
    return await _submit(built["graph"], {"engine": engine, "mode": "t2v"})


async def generate_video_i2v(args: dict[str, Any]) -> dict:
    engine = args.get("engine") or "ltx"
    params = _map_args(args)
    use_vace = bool(params.pop("useVace", False) or args.get("use_vace") or args.get("useVace"))
    if use_vace and engine == "wan":
        ref = params.get("refImageName") or params.get("anchorImageName") or params.get("imageName")
        if not ref:
            raise ValueError("VACE 需要 ref_image_name / image_name（定妆照）")
        params["refImageName"] = ref
        if not params.get("imageName"):
            params["imageName"] = ref
        path = _workflow_path(engine, "vace")
        base = load_workflow(path)
        built = build_vace_i2v(base, params)
        return await _submit(built["graph"], {"engine": engine, "mode": "vace"})
    if not params.get("imageName"):
        raise ValueError("image_name required")
    path = _workflow_path(engine, "i2v")
    base = load_workflow(path)
    built = build_ltx23_i2v(base, params) if engine == "ltx" else build_i2v(base, params)
    return await _submit(built["graph"], {"engine": engine, "mode": "i2v"})


async def generate_video_flf2v(args: dict[str, Any]) -> dict:
    engine = args.get("engine") or "wan"
    params = _map_args(args)
    if not params.get("firstImageName") or not params.get("lastImageName"):
        raise ValueError("first_image_name and last_image_name required")
    if engine == "ltx":
        path = _workflow_path("ltx", "flf2v")
        base = load_workflow(path)
        built = build_ltx23_flf2v(base, params)
    else:
        path = _workflow_path("wan", "flf2v")
        base = load_workflow(path)
        built = build_wan_flf2v(base, params)
    return await _submit(built["graph"], {"engine": engine, "mode": "flf2v"})


def _humanize_comfy_error(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return "ComfyUI 执行失败"
    if "Fault failed: 2" in text:
        return (
            "GPU 显存管理异常（DynamicVRAM 加载模型失败），通常由上次 CUDA 崩溃引起。"
            "请重启 ComfyUI（:8188）后重试。"
        )
    if "Fault failed: 1" in text or "VBAR OOM" in text:
        return "GPU 显存不足（DynamicVRAM）。请重启 ComfyUI 后重试，或降低分辨率（FLF2V 建议 832×480）。"
    if "out of memory" in text.lower() or "Allocation on device" in text:
        return (
            "GPU 显存不足。"
            + (" FLF2V 需同时加载高/低噪两个 14B 模型，720P 峰值较高。" if "flf2v" not in text else "")
            + " 可改 832×480 或重启 ComfyUI 释放显存。"
        )
    return text


async def get_video_task(args: dict[str, Any]) -> dict:
    task_id = args.get("task_id")
    if not task_id:
        raise ValueError("task_id required")
    task = task_store.get(task_id)
    if not task:
        raise ValueError(f"unknown task_id: {task_id}")
    prompt_id = task["prompt_id"]
    async with ComfyClient() as comfy:
        history = await comfy.get_history(prompt_id)
        queue = await comfy.get_queue()
        media = extract_media_from_history(history, prompt_id)
        if media:
            enriched = []
            for m in media:
                item = dict(m)
                item["url"] = comfy.view_url(m["filename"], m.get("subfolder") or "", m.get("type") or "output")
                item["comfy_url"] = comfy.comfy_view_url(m["filename"], m.get("subfolder") or "", m.get("type") or "output")
                enriched.append(item)
            return task_store.update(task_id, status="completed", media=enriched, progress={"value": 1, "max": 1}) or {
                **task,
                "status": "completed",
                "media": enriched,
            }
        entry = history.get(prompt_id) or {}
        status = entry.get("status") or {}
        if status.get("status_str") == "error":
            messages = status.get("messages") or []
            err = "ComfyUI 执行失败"
            for m in messages:
                if isinstance(m, list) and m and m[0] == "execution_error":
                    err = _humanize_comfy_error((m[1] or {}).get("exception_message") or err)
            mode = (task.get("meta") or {}).get("mode")
            if mode == "flf2v" and "832" not in err and "重启 ComfyUI" not in err:
                err = f"{err}（FLF2V 生成失败）"
            return task_store.update(task_id, status="failed", error=err) or {**task, "status": "failed", "error": err}
        qinfo = ComfyClient.is_prompt_in_queue(queue, prompt_id)
        queue_pos = ComfyClient.get_queue_position(queue, prompt_id)
        phase = "running" if qinfo["inRunning"] else "queued" if qinfo["inPending"] else "waiting"
        return task_store.update(task_id, status=phase, queue_pos=queue_pos) or {
            **task,
            "status": phase,
            "queue_pos": queue_pos,
        }
