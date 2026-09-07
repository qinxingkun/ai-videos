from __future__ import annotations

from typing import Any

from .models import (
    FL2VA_MODES,
    REF2VA_MODES,
    ConditionIn,
    JobCreate,
    Mode,
)


class JobBuildError(ValueError):
    pass


def upstream_for_mode(mode: Mode) -> str:
    if mode in FL2VA_MODES:
        return "fl2va"
    if mode in REF2VA_MODES:
        return "ref2va"
    raise JobBuildError(f"unsupported mode: {mode}")


def build_payload(job: JobCreate) -> dict[str, Any]:
    conditions = _build_conditions(job)
    payload: dict[str, Any] = {
        "task": _task_for_mode(job.mode),
        "prompt": job.prompt,
        "conditions": conditions,
        "target": {
            "short_edge": job.short_edge,
            "aspect_ratio": job.aspect_ratio,
            "duration_seconds": job.duration_seconds,
        },
        "seed": job.seed,
    }
    if job.num_inference_steps is not None:
        payload["num_inference_steps"] = job.num_inference_steps
    if job.flow_shift is not None:
        payload["flow_shift"] = job.flow_shift
    if job.audio_flow_shift is not None:
        payload["audio_flow_shift"] = job.audio_flow_shift
    return payload


def _task_for_mode(mode: Mode) -> str:
    if mode == Mode.t2va:
        return "t2va"
    if mode in {Mode.i2va_first, Mode.i2va_last, Mode.fl2va}:
        return "fl2va"
    return "ref2va"


def _build_conditions(job: JobCreate) -> list[dict[str, Any]]:
    mode = job.mode
    conds = job.conditions

    if mode == Mode.t2va:
        return []

    if mode == Mode.i2va_first:
        img = _require_one(conds, "image", "first-frame image")
        return [_keyframe(img.uri, 0)]

    if mode == Mode.i2va_last:
        img = _require_one(conds, "image", "last-frame image")
        # Last frame index is resolved from duration by the runtime when using a large index;
        # official examples use frame_index for first. For last-only, pass a high index.
        last_idx = max(0, int(round(job.duration_seconds * 24)) - 1)
        return [_keyframe(img.uri, last_idx)]

    if mode == Mode.fl2va:
        images = [c for c in conds if c.type == "image"]
        if len(images) < 2:
            raise JobBuildError("fl2va requires first and last frame images")
        last_idx = max(0, int(round(job.duration_seconds * 24)) - 1)
        return [
            _keyframe(images[0].uri, 0),
            _keyframe(images[1].uri, last_idx),
        ]

    if mode == Mode.ref_image:
        images = [c for c in conds if c.type == "image"]
        if not images:
            raise JobBuildError("ref_image requires at least one reference image")
        if len(images) > 9:
            raise JobBuildError("ref_image supports at most 9 images")
        return [_reference(c.type, c.uri) for c in images]

    if mode == Mode.ref_video:
        videos = [c for c in conds if c.type == "video"]
        if not videos:
            raise JobBuildError("ref_video requires at least one reference video")
        if len(videos) > 3:
            raise JobBuildError("ref_video supports at most 3 videos")
        return [_reference(c.type, c.uri) for c in videos]

    if mode == Mode.ref_audio:
        audios = [c for c in conds if c.type == "audio"]
        visuals = [c for c in conds if c.type in {"image", "video"}]
        if not audios:
            raise JobBuildError("ref_audio requires at least one reference audio")
        if not visuals:
            raise JobBuildError("ref_audio requires image or video alongside audio")
        if len(audios) > 3:
            raise JobBuildError("ref_audio supports at most 3 audio clips")
        return [_reference(c.type, c.uri) for c in [*visuals, *audios]]

    if mode == Mode.ref_mixed:
        if not conds:
            raise JobBuildError("ref_mixed requires at least one reference file")
        if len(conds) > 12:
            raise JobBuildError("ref_mixed supports at most 12 files")
        images = sum(1 for c in conds if c.type == "image")
        videos = sum(1 for c in conds if c.type == "video")
        audios = sum(1 for c in conds if c.type == "audio")
        if images > 9 or videos > 3 or audios > 3:
            raise JobBuildError("ref_mixed limits: images<=9, videos<=3, audios<=3")
        if audios and not (images or videos):
            raise JobBuildError("audio cannot be the only reference input")
        return [_reference(c.type, c.uri) for c in conds]

    raise JobBuildError(f"unsupported mode: {mode}")


def _require_one(conds: list[ConditionIn], typ: str, label: str) -> ConditionIn:
    matches = [c for c in conds if c.type == typ]
    if not matches:
        raise JobBuildError(f"{label} is required")
    return matches[0]


def _keyframe(uri: str, frame_index: int) -> dict[str, Any]:
    return {
        "type": "image",
        "uri": uri,
        "role": "keyframe",
        "frame_index": frame_index,
    }


def _reference(typ: str, uri: str) -> dict[str, Any]:
    return {"type": typ, "uri": uri, "role": "reference"}
