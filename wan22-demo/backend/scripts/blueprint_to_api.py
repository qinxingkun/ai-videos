#!/usr/bin/env python3
"""ComfyUI Blueprint 子图 → API prompt JSON。"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def build_link_map(links: list) -> dict:
    to_target = {}
    for link in links or []:
        # blueprint links may be objects or arrays
        if isinstance(link, dict):
            tid, tslot = link["target_id"], link["target_slot"]
            oid, oslot = link["origin_id"], link["origin_slot"]
        else:
            # [id, origin_id, origin_slot, target_id, target_slot, type]
            oid, oslot, tid, tslot = link[1], link[2], link[3], link[4]
        to_target[f"{tid}:{tslot}"] = [str(oid), oslot]
    return to_target


def node_to_api(node: dict, link_map: dict) -> dict:
    inputs = {}
    widget_idx = 0
    widgets = node.get("widgets_values") or []
    for slot, inp in enumerate(node.get("inputs") or []):
        key = inp.get("name")
        link_key = f"{node['id']}:{slot}"
        if link_key in link_map:
            inputs[key] = link_map[link_key]
        elif inp.get("widget"):
            if widget_idx < len(widgets):
                inputs[key] = widgets[widget_idx]
                widget_idx += 1
    return {"class_type": node.get("type"), "inputs": inputs}


def convert(blueprint: dict, subgraph_name: str) -> dict:
    subgraphs = (blueprint.get("definitions") or {}).get("subgraphs") or []
    sg = next((s for s in subgraphs if s.get("name") == subgraph_name), None)
    if sg is None and subgraphs:
        sg = subgraphs[0]
    if not sg:
        raise RuntimeError("subgraph not found")
    link_map = build_link_map(sg.get("links") or [])
    api = {}
    for node in sg.get("nodes") or []:
        ntype = node.get("type") or ""
        if not ntype or ntype.startswith("Primitive"):
            continue
        api[str(node["id"])] = node_to_api(node, link_map)
    return api


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python blueprint_to_api.py <blueprint.json> [subgraphName]", file=sys.stderr)
        return 1
    path = Path(sys.argv[1])
    name = sys.argv[2] if len(sys.argv) > 2 else "Text to Video (LTX-2.3)"
    blueprint = json.loads(path.read_text(encoding="utf-8"))
    api = convert(blueprint, name)
    sys.stdout.write(json.dumps(api, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
