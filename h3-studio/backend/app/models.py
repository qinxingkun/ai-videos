from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Mode(str, Enum):
    t2va = "t2va"
    i2va_first = "i2va_first"
    i2va_last = "i2va_last"
    fl2va = "fl2va"
    ref_image = "ref_image"
    ref_video = "ref_video"
    ref_audio = "ref_audio"
    ref_mixed = "ref_mixed"


class ConditionIn(BaseModel):
    type: Literal["image", "video", "audio"]
    uri: str
    role: Literal["keyframe", "reference"] = "reference"
    frame_index: int | None = None


class JobCreate(BaseModel):
    mode: Mode
    prompt: str = Field(min_length=1)
    conditions: list[ConditionIn] = Field(default_factory=list)
    seed: int = 42
    # MiniMax-H3 currently requires short_edge == 768.
    short_edge: int = Field(default=768, ge=768, le=768)
    aspect_ratio: str = "16:9"
    duration_seconds: float = Field(default=5, ge=4, le=15)
    num_inference_steps: int | None = Field(default=None, ge=1, le=100)
    flow_shift: float | None = None
    audio_flow_shift: float | None = None


class JobRecord(BaseModel):
    id: str
    mode: Mode
    upstream: str
    task: str
    status: str = "queued"
    progress: int | float | None = 0
    created_at: int | None = None
    size: str | None = None
    seconds: str | float | None = None
    inference_time_s: float | None = None
    peak_memory_mb: float | None = None
    error: Any = None
    file_path: str | None = None
    prompt: str | None = None


FL2VA_MODES = {Mode.t2va, Mode.i2va_first, Mode.i2va_last, Mode.fl2va}
REF2VA_MODES = {Mode.ref_image, Mode.ref_video, Mode.ref_audio, Mode.ref_mixed}
