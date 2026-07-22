from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

OVERRIDES = {
    "t2v": {
        "positivePrompt": None,
        "negativePrompt": None,
        "latent": None,
        "samplers": None,
    },
    "i2v": {
        "positivePrompt": None,
        "negativePrompt": None,
        "wanI2V": None,
        "loadImage": None,
        "samplers": None,
        "anchorImage": "620",
        "imageBlend": "621",
    },
    "vace": {
        "positivePrompt": "5",
        "negativePrompt": "5",
        "loadRef": "6",
        "loadStart": "7",
        "vaceEncode": "8",
        "sampler": "9",
        "saveVideo": "11",
    },
    "flf2v": {
        "positivePrompt": None,
        "negativePrompt": None,
        "wanFlf2v": None,
        "loadImageFirst": None,
        "loadImageLast": None,
        "samplers": None,
    },
    "ltx23": {
        "positivePrompt": "305",
        "negativePrompt": "315",
        "videoLatent": "297",
        "audioLatent": "307",
        "conditioning": "306",
        "noiseSeeds": ["279", "278"],
    },
    "ltx23i2v": {
        "positivePrompt": "305",
        "negativePrompt": "315",
        "videoLatent": "297",
        "audioLatent": "307",
        "conditioning": "306",
        "noiseSeeds": ["279", "278"],
        "loadImage": "322",
        "resizeImage": "292",
        "preprocess": "291",
        "anchorImage": "323",
        "imageBlend": "324",
    },
    "ltx23flf2v": {
        "positivePrompt": "222",
        "negativePrompt": "217",
        "videoLatent": "201",
        "audioLatent": "197",
        "conditioning": "202",
        "noiseSeeds": ["196"],
        "loadImageFirst": "801",
        "loadImageLast": "802",
        "resizeFirst": "213",
        "resizeLast": "214",
    },
}

CLASS = {
    "samplers": ["KSamplerAdvanced", "KSampler", "SamplerCustomAdvanced"],
    "clipTextEncode": ["CLIPTextEncode"],
    "t2vLatent": ["EmptyHunyuanLatentVideo", "EmptySD3LatentImage", "EmptyLatentImage", "EmptyLTXVLatentVideo"],
    "wanI2V": ["WanImageToVideo"],
    "wanFlf2v": ["WanFirstLastFrameToVideo"],
    "loadImage": ["LoadImage", "LoadImageOutput"],
    "saveVideo": ["SaveVideo", "VHS_VideoCombine", "SaveWEBM"],
}


def is_link(v: Any) -> bool:
    return isinstance(v, list) and len(v) == 2 and isinstance(v[1], int)


def sanitize_prompt_graph(graph: dict) -> dict:
    clean = {}
    for nid, node in (graph or {}).items():
        if isinstance(node, dict) and node.get("class_type"):
            clean[nid] = node
    return clean


def clone_graph(graph: dict) -> dict:
    return sanitize_prompt_graph(copy.deepcopy(graph))


def load_workflow(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return sanitize_prompt_graph(json.load(f))


def entries(graph: dict) -> list[tuple[str, dict]]:
    return [(nid, node) for nid, node in graph.items() if isinstance(node, dict) and node.get("class_type")]


def find_by_class(graph: dict, class_names: list[str]) -> list[dict]:
    names = set(class_names)
    return [{"id": nid, "node": node} for nid, node in entries(graph) if node.get("class_type") in names]


def get_node(graph: dict, nid: str | None) -> dict | None:
    return graph.get(nid) if nid is not None else None


def resolve_upstream(graph: dict, start_id: str, input_name: str, target_classes: list[str], depth: int = 0) -> str | None:
    if depth > 8:
        return None
    node = get_node(graph, start_id)
    if not node or not node.get("inputs"):
        return None
    link = node["inputs"].get(input_name)
    if not is_link(link):
        return None
    upstream_id = link[0]
    upstream = get_node(graph, str(upstream_id))
    if not upstream:
        return None
    if upstream.get("class_type") in target_classes:
        return str(upstream_id)
    keys = list(upstream.get("inputs") or {})
    ordered = [input_name, *[k for k in keys if k != input_name]] if input_name in keys else keys
    for key in ordered:
        if is_link(upstream["inputs"].get(key)):
            found = resolve_upstream(graph, str(upstream_id), key, target_classes, depth + 1)
            if found:
                return found
    return None


def locate_prompts(graph: dict, sampler_ids: list[str], ov: dict) -> tuple[str | None, str | None]:
    positive = ov.get("positivePrompt")
    negative = ov.get("negativePrompt")
    for sid in sampler_ids:
        if not positive:
            positive = resolve_upstream(graph, sid, "positive", CLASS["clipTextEncode"])
        if not negative:
            negative = resolve_upstream(graph, sid, "negative", CLASS["clipTextEncode"])
        if positive and negative:
            break
    if not positive or not negative:
        encs = [e["id"] for e in find_by_class(graph, CLASS["clipTextEncode"])]
        if not positive and encs:
            positive = encs[0]
        if not negative:
            negative = next((eid for eid in encs if eid != positive), None)
    return positive, negative


def set_input(graph: dict, nid: str | None, key: str, value: Any) -> bool:
    node = get_node(graph, nid)
    if not node or "inputs" not in node:
        return False
    if key in node["inputs"] and not is_link(node["inputs"][key]):
        node["inputs"][key] = value
        return True
    if not is_link(node["inputs"].get(key)):
        node["inputs"][key] = value
        return True
    return False


def force_set_input(graph: dict, nid: str | None, key: str, value: Any) -> bool:
    node = get_node(graph, nid)
    if not node or "inputs" not in node:
        return False
    node["inputs"][key] = value
    return True


def apply_sampler_params(graph: dict, sampler_ids: list[str], params: dict) -> None:
    seed = params.get("seed")
    steps = params.get("steps")
    cfg = params.get("cfg")
    for sid in sampler_ids:
        node = get_node(graph, sid)
        if not node:
            continue
        if seed is not None:
            if "noise_seed" in node["inputs"]:
                set_input(graph, sid, "noise_seed", seed)
            elif "seed" in node["inputs"]:
                set_input(graph, sid, "seed", seed)
        if steps is not None and "steps" in node["inputs"]:
            set_input(graph, sid, "steps", steps)
        if cfg is not None and "cfg" in node["inputs"]:
            set_input(graph, sid, "cfg", cfg)


def find_create_video(graph: dict) -> str | None:
    found = find_by_class(graph, ["CreateVideo"])
    return found[0]["id"] if found else None


def find_save_video(graph: dict) -> str | None:
    found = find_by_class(graph, CLASS["saveVideo"])
    return found[0]["id"] if found else None


def set_fps(graph: dict, fps: Any) -> None:
    nid = find_create_video(graph)
    if nid is not None and fps is not None:
        force_set_input(graph, nid, "fps", fps)


def set_filename_prefix(graph: dict, prefix: Any) -> None:
    nid = find_save_video(graph)
    if nid is not None and prefix is not None:
        set_input(graph, nid, "filename_prefix", prefix)


def apply_lightx2v_defaults(graph: dict, sampler_ids: list[str] | None = None) -> None:
    ids = sampler_ids or [s["id"] for s in find_by_class(graph, CLASS["samplers"])]
    samplers = []
    for sid in ids:
        node = get_node(graph, sid)
        if node and node.get("class_type") == "KSamplerAdvanced":
            samplers.append({"id": sid, "node": node})
    samplers.sort(key=lambda s: s["node"]["inputs"].get("start_at_step", 0))
    steps, cfg, split = 4, 1.0, 2
    for item in samplers:
        sid, node = item["id"], item["node"]
        set_input(graph, sid, "steps", steps)
        set_input(graph, sid, "cfg", cfg)
        start = node["inputs"].get("start_at_step", 0)
        if start == 0:
            set_input(graph, sid, "end_at_step", split)
            set_input(graph, sid, "add_noise", "enable")
            set_input(graph, sid, "return_with_leftover_noise", "enable")
        else:
            set_input(graph, sid, "start_at_step", split)
            set_input(graph, sid, "end_at_step", steps)
            set_input(graph, sid, "add_noise", "disable")
            set_input(graph, sid, "return_with_leftover_noise", "disable")


def apply_anchor_blend(graph: dict, ov: dict, params: dict) -> None:
    """锚点软拉回：将链式起始图与角色定妆照按 anchor_blend_weight 混合后再送入 I2V。

    blend_factor=0（默认）时 ImageBlend 输出等价于直通链式图，向后兼容旧工作流行为；
    weight>0 时逐步把外观拉回参考图，缓解长链人设漂移，无需切换到 FLF2V 打断运镜。
    """
    anchor_id = ov.get("anchorImage")
    blend_id = ov.get("imageBlend")
    if not anchor_id or not blend_id:
        return
    if params.get("anchorImageName"):
        force_set_input(graph, anchor_id, "image", params["anchorImageName"])
    weight = params.get("anchorBlendWeight")
    if weight is not None:
        force_set_input(graph, blend_id, "blend_factor", max(0.0, min(1.0, float(weight))))


def build_t2v(base_graph: dict, params: dict) -> dict:
    graph = clone_graph(base_graph)
    ov = OVERRIDES["t2v"]
    sampler_ids = ov.get("samplers") or [s["id"] for s in find_by_class(graph, CLASS["samplers"])]
    positive, negative = locate_prompts(graph, sampler_ids, ov)
    if positive and params.get("positivePrompt") is not None:
        set_input(graph, positive, "text", params["positivePrompt"])
    if negative and params.get("negativePrompt") is not None:
        set_input(graph, negative, "text", params["negativePrompt"])
    latent_id = ov.get("latent") or (find_by_class(graph, CLASS["t2vLatent"])[0]["id"] if find_by_class(graph, CLASS["t2vLatent"]) else None)
    if latent_id:
        if params.get("width") is not None:
            set_input(graph, latent_id, "width", params["width"])
        if params.get("height") is not None:
            set_input(graph, latent_id, "height", params["height"])
        if params.get("length") is not None:
            set_input(graph, latent_id, "length", params["length"])
    if params.get("useLightX2V"):
        apply_lightx2v_defaults(graph, sampler_ids)
        if params.get("seed") is not None:
            apply_sampler_params(graph, sampler_ids, {"seed": params["seed"]})
    else:
        apply_sampler_params(graph, sampler_ids, params)
    if params.get("fps") is not None:
        set_fps(graph, params["fps"])
    if params.get("filenamePrefix") is not None:
        set_filename_prefix(graph, params["filenamePrefix"])
    return {"graph": graph, "located": {"positive": positive, "negative": negative, "latentId": latent_id, "samplerIds": sampler_ids}}


def build_ltx23_t2v(base_graph: dict, params: dict) -> dict:
    graph = clone_graph(base_graph)
    ov = OVERRIDES["ltx23"]
    positive = ov.get("positivePrompt") or "305"
    negative = ov.get("negativePrompt") or "315"
    video_latent = ov.get("videoLatent") or "297"
    audio_latent = ov.get("audioLatent") or "307"
    conditioning = ov.get("conditioning") or "306"
    noise_ids = ov.get("noiseSeeds") or ["279", "278"]
    fps = params.get("fps", 24)
    if positive and params.get("positivePrompt") is not None:
        force_set_input(graph, positive, "text", params["positivePrompt"])
    if negative and params.get("negativePrompt") is not None:
        force_set_input(graph, negative, "text", params["negativePrompt"])
    if params.get("width") is not None:
        force_set_input(graph, video_latent, "width", params["width"])
    if params.get("height") is not None:
        force_set_input(graph, video_latent, "height", params["height"])
    if params.get("length") is not None:
        force_set_input(graph, video_latent, "length", params["length"])
        force_set_input(graph, audio_latent, "frames_number", params["length"])
    force_set_input(graph, audio_latent, "frame_rate", fps)
    force_set_input(graph, conditioning, "frame_rate", fps)
    set_fps(graph, fps)
    if params.get("seed") is not None:
        for nid in noise_ids:
            force_set_input(graph, nid, "noise_seed", params["seed"])
    if params.get("filenamePrefix") is not None:
        set_filename_prefix(graph, params["filenamePrefix"])
    return {"graph": graph, "located": {"positive": positive, "negative": negative, "videoLatent": video_latent, "audioLatent": audio_latent, "noiseIds": noise_ids}}


def build_ltx23_i2v(base_graph: dict, params: dict) -> dict:
    graph = clone_graph(base_graph)
    ov = OVERRIDES["ltx23i2v"]
    positive = ov.get("positivePrompt") or "305"
    negative = ov.get("negativePrompt") or "315"
    video_latent = ov.get("videoLatent") or "297"
    audio_latent = ov.get("audioLatent") or "307"
    conditioning = ov.get("conditioning") or "306"
    noise_ids = ov.get("noiseSeeds") or ["279", "278"]
    load_image = ov.get("loadImage") or "322"
    resize_image = ov.get("resizeImage") or "292"
    fps = params.get("fps", 24)
    width = params.get("width", 768)
    height = params.get("height", 512)
    if positive and params.get("positivePrompt") is not None:
        force_set_input(graph, positive, "text", params["positivePrompt"])
    if negative and params.get("negativePrompt") is not None:
        force_set_input(graph, negative, "text", params["negativePrompt"])
    if params.get("width") is not None:
        force_set_input(graph, video_latent, "width", params["width"])
    if params.get("height") is not None:
        force_set_input(graph, video_latent, "height", params["height"])
    if params.get("length") is not None:
        force_set_input(graph, video_latent, "length", params["length"])
        force_set_input(graph, audio_latent, "frames_number", params["length"])
    force_set_input(graph, audio_latent, "frame_rate", fps)
    force_set_input(graph, conditioning, "frame_rate", fps)
    set_fps(graph, fps)
    if resize_image:
        force_set_input(graph, resize_image, "resize_type.width", width)
        force_set_input(graph, resize_image, "resize_type.height", height)
    if load_image and params.get("imageName"):
        force_set_input(graph, load_image, "image", params["imageName"])
    apply_anchor_blend(graph, ov, params)
    if params.get("i2vStrength") is not None:
        for nid in ["298", "290"]:
            node = get_node(graph, nid)
            if node and "strength" in (node.get("inputs") or {}):
                force_set_input(graph, nid, "strength", params["i2vStrength"])
    if params.get("seed") is not None:
        for nid in noise_ids:
            force_set_input(graph, nid, "noise_seed", params["seed"])
    if params.get("filenamePrefix") is not None:
        set_filename_prefix(graph, params["filenamePrefix"])
    return {"graph": graph, "located": {"positive": positive, "negative": negative, "videoLatent": video_latent, "audioLatent": audio_latent, "noiseIds": noise_ids, "loadImage": load_image}}


def build_ltx23_flf2v(base_graph: dict, params: dict) -> dict:
    graph = clone_graph(base_graph)
    ov = OVERRIDES["ltx23flf2v"]
    positive = ov.get("positivePrompt") or "222"
    negative = ov.get("negativePrompt") or "217"
    video_latent = ov.get("videoLatent") or "201"
    audio_latent = ov.get("audioLatent") or "197"
    conditioning = ov.get("conditioning") or "202"
    noise_ids = ov.get("noiseSeeds") or ["196"]
    load_first = ov.get("loadImageFirst") or "801"
    load_last = ov.get("loadImageLast") or "802"
    fps = params.get("fps", 24)
    width = params.get("width", 768)
    height = params.get("height", 512)
    if positive and params.get("positivePrompt") is not None:
        force_set_input(graph, positive, "text", params["positivePrompt"])
    if negative and params.get("negativePrompt") is not None:
        force_set_input(graph, negative, "text", params["negativePrompt"])
    if params.get("width") is not None:
        force_set_input(graph, video_latent, "width", width)
    if params.get("height") is not None:
        force_set_input(graph, video_latent, "height", height)
    if params.get("length") is not None:
        force_set_input(graph, video_latent, "length", params["length"])
        force_set_input(graph, audio_latent, "frames_number", params["length"])
    force_set_input(graph, audio_latent, "frame_rate", fps)
    force_set_input(graph, conditioning, "frame_rate", fps)
    set_fps(graph, fps)
    for rid in [ov.get("resizeFirst") or "213", ov.get("resizeLast") or "214"]:
        if rid and get_node(graph, rid):
            force_set_input(graph, rid, "resize_type.width", width)
            force_set_input(graph, rid, "resize_type.height", height)
    if load_first and params.get("firstImageName"):
        force_set_input(graph, load_first, "image", params["firstImageName"])
    if load_last and params.get("lastImageName"):
        force_set_input(graph, load_last, "image", params["lastImageName"])
    if params.get("seed") is not None:
        for nid in noise_ids:
            force_set_input(graph, nid, "noise_seed", params["seed"])
    if params.get("filenamePrefix") is not None:
        set_filename_prefix(graph, params["filenamePrefix"])
    return {"graph": graph, "located": {"positive": positive, "negative": negative, "videoLatent": video_latent, "audioLatent": audio_latent, "noiseIds": noise_ids, "loadFirst": load_first, "loadLast": load_last}}


def build_i2v(base_graph: dict, params: dict) -> dict:
    graph = clone_graph(base_graph)
    ov = OVERRIDES["i2v"]
    sampler_ids = ov.get("samplers") or [s["id"] for s in find_by_class(graph, CLASS["samplers"])]
    positive, negative = locate_prompts(graph, sampler_ids, ov)
    if positive and params.get("positivePrompt") is not None:
        set_input(graph, positive, "text", params["positivePrompt"])
    if negative and params.get("negativePrompt") is not None:
        set_input(graph, negative, "text", params["negativePrompt"])
    wan_found = find_by_class(graph, CLASS["wanI2V"])
    wan_id = ov.get("wanI2V") or (wan_found[0]["id"] if wan_found else None)
    if wan_id:
        if params.get("width") is not None:
            force_set_input(graph, wan_id, "width", params["width"])
        if params.get("height") is not None:
            force_set_input(graph, wan_id, "height", params["height"])
        if params.get("length") is not None:
            force_set_input(graph, wan_id, "length", params["length"])
    load_image_id = ov.get("loadImage")
    if not load_image_id and wan_id:
        load_image_id = resolve_upstream(graph, wan_id, "start_image", CLASS["loadImage"])
    if not load_image_id:
        loads = find_by_class(graph, CLASS["loadImage"])
        load_image_id = loads[0]["id"] if loads else None
    if load_image_id and params.get("imageName"):
        force_set_input(graph, load_image_id, "image", params["imageName"])
    apply_anchor_blend(graph, ov, params)
    apply_sampler_params(graph, sampler_ids, params)
    if params.get("fps") is not None:
        set_fps(graph, params["fps"])
    return {"graph": graph, "located": {"positive": positive, "negative": negative, "wanId": wan_id, "loadImageId": load_image_id, "samplerIds": sampler_ids}}


def build_vace_i2v(base_graph: dict, params: dict) -> dict:
    """Wan-VACE 参考图引导：ref_images=定妆照；input_frames=场景起始（可与定妆照相同）。"""
    graph = clone_graph(base_graph)
    ov = OVERRIDES["vace"]
    text_id = ov["positivePrompt"]
    if params.get("positivePrompt") is not None:
        force_set_input(graph, text_id, "positive_prompt", params["positivePrompt"])
    if params.get("negativePrompt") is not None:
        force_set_input(graph, text_id, "negative_prompt", params["negativePrompt"])

    ref_name = params.get("refImageName") or params.get("anchorImageName") or params.get("imageName")
    start_name = params.get("imageName") or ref_name
    if ref_name:
        force_set_input(graph, ov["loadRef"], "image", ref_name)
    if start_name:
        force_set_input(graph, ov["loadStart"], "image", start_name)

    vace_id = ov["vaceEncode"]
    if params.get("width") is not None:
        force_set_input(graph, vace_id, "width", params["width"])
    if params.get("height") is not None:
        force_set_input(graph, vace_id, "height", params["height"])
    if params.get("length") is not None:
        force_set_input(graph, vace_id, "num_frames", params["length"])
    if params.get("vaceStrength") is not None:
        force_set_input(graph, vace_id, "strength", params["vaceStrength"])

    sampler_id = ov["sampler"]
    if params.get("seed") is not None:
        force_set_input(graph, sampler_id, "seed", params["seed"])
    if params.get("steps") is not None:
        force_set_input(graph, sampler_id, "steps", params["steps"])
    if params.get("cfg") is not None:
        force_set_input(graph, sampler_id, "cfg", params["cfg"])

    if params.get("filenamePrefix") is not None:
        force_set_input(graph, ov["saveVideo"], "filename_prefix", params["filenamePrefix"])
    if params.get("fps") is not None:
        force_set_input(graph, ov["saveVideo"], "frame_rate", params["fps"])

    return {
        "graph": graph,
        "located": {
            "textId": text_id,
            "loadRef": ov["loadRef"],
            "loadStart": ov["loadStart"],
            "vaceEncode": vace_id,
            "samplerId": sampler_id,
        },
    }


def build_wan_flf2v(base_graph: dict, params: dict) -> dict:
    graph = clone_graph(base_graph)
    ov = OVERRIDES["flf2v"]
    sampler_ids = ov.get("samplers") or [s["id"] for s in find_by_class(graph, CLASS["samplers"])]
    positive, negative = locate_prompts(graph, sampler_ids, ov)
    if positive and params.get("positivePrompt") is not None:
        set_input(graph, positive, "text", params["positivePrompt"])
    if negative and params.get("negativePrompt") is not None:
        set_input(graph, negative, "text", params["negativePrompt"])
    wan_found = find_by_class(graph, CLASS["wanFlf2v"])
    wan_id = ov.get("wanFlf2v") or (wan_found[0]["id"] if wan_found else None)
    if wan_id:
        if params.get("width") is not None:
            force_set_input(graph, wan_id, "width", params["width"])
        if params.get("height") is not None:
            force_set_input(graph, wan_id, "height", params["height"])
        if params.get("length") is not None:
            force_set_input(graph, wan_id, "length", params["length"])
    load_first_id = ov.get("loadImageFirst")
    load_last_id = ov.get("loadImageLast")
    if wan_id:
        if not load_first_id:
            load_first_id = resolve_upstream(graph, wan_id, "start_image", CLASS["loadImage"])
        if not load_last_id:
            load_last_id = resolve_upstream(graph, wan_id, "end_image", CLASS["loadImage"])
    loads = find_by_class(graph, CLASS["loadImage"])
    if not load_first_id and loads:
        load_first_id = loads[0]["id"]
    if not load_last_id and len(loads) > 1:
        load_last_id = loads[1]["id"]
    if load_first_id and params.get("firstImageName"):
        force_set_input(graph, load_first_id, "image", params["firstImageName"])
    if load_last_id and params.get("lastImageName"):
        force_set_input(graph, load_last_id, "image", params["lastImageName"])
    apply_sampler_params(graph, sampler_ids, params)
    if params.get("fps") is not None:
        set_fps(graph, params["fps"])
    if params.get("filenamePrefix") is not None:
        set_filename_prefix(graph, params["filenamePrefix"])
    return {
        "graph": graph,
        "located": {
            "positive": positive,
            "negative": negative,
            "wanId": wan_id,
            "loadFirstId": load_first_id,
            "loadLastId": load_last_id,
            "samplerIds": sampler_ids,
        },
    }


def extract_media_from_history(history: dict, prompt_id: str) -> list[dict]:
    entry = (history or {}).get(prompt_id)
    if not entry or not entry.get("outputs"):
        return []
    results = []
    for node_id, out in entry["outputs"].items():
        for key, arr in out.items():
            if not isinstance(arr, list):
                continue
            for item in arr:
                if isinstance(item, dict) and item.get("filename"):
                    filename = item["filename"]
                    is_video = bool(__import__("re").search(r"\.(mp4|webm|mkv|mov|gif)$", filename, __import__("re").I))
                    results.append(
                        {
                            "nodeId": node_id,
                            "kind": "video" if is_video else "image",
                            "filename": filename,
                            "subfolder": item.get("subfolder") or "",
                            "type": item.get("type") or "output",
                        }
                    )
    results.sort(key=lambda x: 0 if x["kind"] == "video" else 1)
    return results
