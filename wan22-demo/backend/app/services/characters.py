from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import get_settings


def _path() -> Path:
    return get_settings().characters_file


def load_characters() -> list[dict[str, Any]]:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_characters(list_: list[dict[str, Any]]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(list_, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def upsert_character(id_: str, name: str, character: dict | None = None) -> dict:
    from datetime import datetime, timezone

    list_ = [c for c in load_characters() if c.get("id") != id_]
    item = {
        "id": id_,
        "name": name,
        "character": character or {},
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    list_.append(item)
    save_characters(list_)
    return {"ok": True}


def delete_character(id_: str) -> dict:
    list_ = [c for c in load_characters() if c.get("id") != id_]
    save_characters(list_)
    return {"ok": True}
