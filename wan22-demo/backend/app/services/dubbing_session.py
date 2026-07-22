from __future__ import annotations

import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.services.face_tracking import (
    bind_characters_to_tracks,
    build_face_atlas,
    public_face_atlas,
)
from app.services.media_ops import dub_media, resolve_video_path
from app.services.visual_master import create_visual_master


class DubbingSessionError(RuntimeError):
    """Structured dubbing error that maps cleanly to HTTP responses."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        session_id: str | None = None,
        utterance_ids: list[str] | None = None,
        issues: list[str] | None = None,
        http_status: int = 500,
    ):
        super().__init__(message)
        self.code = code
        self.session_id = session_id
        self.utterance_ids = utterance_ids or []
        self.issues = issues or [message]
        self.http_status = http_status

    def to_detail(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": str(self),
            "sessionId": self.session_id,
            "utteranceIds": self.utterance_ids,
            "issues": self.issues,
        }


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _classify_render_exception(exc: Exception, *, session_id: str) -> DubbingSessionError:
    message = str(exc)
    if isinstance(exc, DubbingSessionError):
        return exc
    if message.startswith("binding_required:"):
        utterance_ids = [part.strip() for part in message.split(":", 1)[1].split(",") if part.strip()]
        return DubbingSessionError(
            message,
            code="BINDING_REQUIRED",
            session_id=session_id,
            utterance_ids=utterance_ids,
            issues=utterance_ids or [message],
            http_status=409,
        )
    if "required LatentSync" in message or "faceTrackId is required" in message:
        return DubbingSessionError(
            message,
            code="REQUIRED_LIPSYNC_FAILED",
            session_id=session_id,
            issues=[message],
            http_status=422,
        )
    if message.startswith("AV QA failed:"):
        issues = [part.strip() for part in message.split(":", 1)[1].split(";") if part.strip()]
        utterance_ids = re.findall(r"utterance[_ ]?([A-Za-z0-9_-]+)", message, flags=re.I)
        return DubbingSessionError(
            message,
            code="AV_QA_FAILED",
            session_id=session_id,
            utterance_ids=utterance_ids,
            issues=issues or [message],
            http_status=422,
        )
    return DubbingSessionError(
        message,
        code="RENDER_FAILED",
        session_id=session_id,
        issues=[message],
        http_status=500,
    )


def _session_dir(settings: Settings, session_id: str) -> Path:
    if not session_id or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for ch in session_id):
        raise ValueError("invalid sessionId")
    return settings.dubbing_sessions_dir / session_id


def _resolve_media(settings: Settings, media: dict[str, Any]) -> Path:
    if media.get("path"):
        path = Path(media["path"]).resolve()
    else:
        path = resolve_video_path(
            settings,
            filename=media.get("filename") or "",
            subfolder=media.get("subfolder", "video"),
            type_=media.get("type", "output"),
        )
    if not path.is_file():
        raise RuntimeError(f"Video not found: {path}")
    return path


def _resolve_reference(settings: Settings, name: str | None) -> Path | None:
    if not name:
        return None
    candidate = (settings.input_dir / name).resolve()
    try:
        candidate.relative_to(settings.input_dir.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def _cleanup_expired_sessions(settings: Settings) -> None:
    root = settings.dubbing_sessions_dir
    if not root.is_dir():
        return
    cutoff = time.time() - settings.dubbing_session_ttl_hours * 3600
    for directory in root.iterdir():
        manifest = directory / "manifest.json"
        try:
            created = json.loads(manifest.read_text(encoding="utf-8")).get("createdAt", 0)
        except Exception:
            created = directory.stat().st_mtime
        if created < cutoff:
            shutil.rmtree(directory, ignore_errors=True)


async def analyze_dub_session(
    body: dict[str, Any],
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    _cleanup_expired_sessions(settings)
    source = _resolve_media(settings, body["media"])
    session_id = f"dub_{int(time.time())}_{uuid.uuid4().hex[:10]}"
    directory = _session_dir(settings, session_id)
    tracks_dir = directory / "tracks"
    directory.mkdir(parents=True, exist_ok=False)
    master = directory / "visual_master.mp4"
    started = time.perf_counter()
    visual = await create_visual_master(source, master, settings=settings)
    visual_seconds = time.perf_counter() - started
    atlas_started = time.perf_counter()
    if body.get("faceBindingMode") == "off":
        atlas_internal = {
            "ok": True,
            "tracks": [],
            "totalFrames": None,
            "skipped": True,
            "reason": "face binding disabled",
        }
    else:
        atlas_internal = build_face_atlas(master, output_dir=tracks_dir, settings=settings)
    atlas_seconds = time.perf_counter() - atlas_started
    bindings = bind_characters_to_tracks(
        body.get("characters") or [],
        atlas_internal,
        settings=settings,
        reference_resolver=lambda name: _resolve_reference(settings, name),
        mode=body.get("faceBindingMode", "auto"),
    )
    atlas = public_face_atlas(atlas_internal)
    status = (
        "awaiting_binding"
        if any(binding["status"] == "binding_required" for binding in bindings)
        else "analyzed"
    )
    manifest = {
        "version": 1,
        "sessionId": session_id,
        "status": status,
        "createdAt": time.time(),
        "source": str(source),
        "visualMaster": visual,
        "visualMasterPath": str(master),
        "faceAtlas": atlas,
        "characters": body.get("characters") or [],
        "bindings": bindings,
        "metrics": {
            "visualMasterSeconds": round(visual_seconds, 3),
            "faceAtlasSeconds": round(atlas_seconds, 3),
            "faceTrackCount": len(atlas.get("tracks") or []),
            "bindingRequiredCount": sum(
                binding["status"] == "binding_required" for binding in bindings
            ),
        },
    }
    _atomic_json(directory / "manifest.json", manifest)
    return manifest


def load_dub_session(session_id: str, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    path = _session_dir(settings, session_id) / "manifest.json"
    if not path.is_file():
        raise RuntimeError(f"dubbing session not found: {session_id}")
    return json.loads(path.read_text(encoding="utf-8"))


async def render_dub_session(
    body: dict[str, Any],
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    session_id = body["sessionId"]
    directory = _session_dir(settings, session_id)
    manifest = load_dub_session(session_id, settings)
    characters = body.get("characters") or manifest.get("characters") or []
    atlas = manifest.get("faceAtlas") or {}
    overrides = body.get("bindingOverrides") or {}
    track_ids = {track["id"] for track in atlas.get("tracks") or []}
    bindings = [dict(item) for item in manifest.get("bindings") or []]
    by_speaker_binding = {item["speakerId"]: item for item in bindings}
    claimed = {
        item["faceTrackId"]
        for item in bindings
        if item.get("faceTrackId") and item["speakerId"] not in overrides
    }
    for speaker_id, track_id in overrides.items():
        if track_id not in track_ids:
            raise RuntimeError(f"unknown faceTrackId override: {track_id}")
        if track_id in claimed:
            raise RuntimeError(f"faceTrackId already bound: {track_id}")
        claimed.add(track_id)
        binding = by_speaker_binding.setdefault(
            speaker_id, {"speakerId": speaker_id}
        )
        binding.update(
            {
                "faceTrackId": track_id,
                "confidence": 1.0,
                "status": "manual",
                "reason": None,
            }
        )
    bindings = list(by_speaker_binding.values())
    binding_by_speaker = {item["speakerId"]: item for item in bindings}
    utterances = []
    for utterance in body.get("utterances") or []:
        binding = binding_by_speaker.get(utterance["speakerId"]) or {}
        utterances.append(
            {
                **utterance,
                "faceTrackId": utterance.get("faceTrackId") or binding.get("faceTrackId"),
                "bindingConfidence": binding.get("confidence"),
            }
        )
    required_unbound = [
        utterance["id"]
        for utterance in utterances
        if utterance.get("lipSyncPolicy") == "required" and not utterance.get("faceTrackId")
    ]
    if required_unbound:
        error = DubbingSessionError(
            "binding_required: " + ", ".join(required_unbound),
            code="BINDING_REQUIRED",
            session_id=session_id,
            utterance_ids=required_unbound,
            issues=required_unbound,
            http_status=409,
        )
        manifest.update(
            {
                "status": "awaiting_binding",
                "bindings": bindings,
                "lastError": error.to_detail(),
                "error": str(error),
            }
        )
        _atomic_json(directory / "manifest.json", manifest)
        raise error

    output_name = body.get("output") or f"dub_{session_id}.mp4"
    manifest.update(
        {
            "status": "rendering",
            "bindings": bindings,
            "utterances": utterances,
            "lastError": None,
            "error": None,
        }
    )
    _atomic_json(directory / "manifest.json", manifest)
    try:
        render_started = time.perf_counter()
        result = await dub_media(
            {
                "path": manifest["source"],
                "_visualMasterPath": manifest["visualMasterPath"],
                "_visualMaster": manifest["visualMaster"],
                "_faceAtlas": atlas,
                "characters": characters,
                "utterances": utterances,
                "output": output_name,
                "sampleRate": 48_000,
            },
            settings=settings,
        )
        result.setdefault("metrics", {})["renderSeconds"] = round(
            time.perf_counter() - render_started, 3
        )
        manifest.update({"status": "done", "result": result, "lastError": None, "error": None})
        _atomic_json(directory / "manifest.json", manifest)
        return {**result, "sessionId": session_id, "bindings": bindings, "faceAtlas": atlas}
    except Exception as exc:
        error = _classify_render_exception(exc, session_id=session_id)
        manifest.update(
            {
                "status": "error",
                "error": str(error),
                "lastError": error.to_detail(),
            }
        )
        _atomic_json(directory / "manifest.json", manifest)
        raise error from exc


def track_thumbnail_path(
    session_id: str,
    filename: str,
    settings: Settings | None = None,
) -> Path:
    settings = settings or get_settings()
    if Path(filename).name != filename:
        raise ValueError("invalid thumbnail filename")
    path = _session_dir(settings, session_id) / "tracks" / filename
    if not path.is_file():
        raise RuntimeError("track thumbnail not found")
    return path
