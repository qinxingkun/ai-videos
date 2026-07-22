from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class VideoGenerateRequest(BaseModel):
    prompt: str
    negative_prompt: str = ""
    engine: str = "ltx"
    width: int | None = None
    height: int | None = None
    length: int | None = None
    fps: int | None = None
    seed: int | None = None
    steps: int | None = None
    cfg: float | None = None
    filename_prefix: str | None = None
    use_lightx2v: bool = False
    image_name: str | None = None
    first_image_name: str | None = None
    last_image_name: str | None = None
    i2v_strength: float | None = None
    anchor_image_name: str | None = None
    anchor_blend_weight: float | None = None
    # Wan-VACE：参考图引导 I2V（定妆照 → ref_images）
    use_vace: bool = False
    ref_image_name: str | None = None
    vace_strength: float | None = None


class ImageGenerateRequest(BaseModel):
    prompt: str
    negative_prompt: str = (
        "低分辨率，低画质，肢体畸形，手指畸形，画面过饱和，蜡像感，人脸无细节，"
        "过度光滑，画面具有AI感。构图混乱。文字模糊，扭曲。"
    )
    width: int = 1328
    height: int = 1328
    seed: int | None = None
    steps: int = 50
    cfg: float = 4.0
    turbo: bool = False
    aspect_ratio: str | None = None
    filename_prefix: str | None = "qwen_t2i"


class ExtractFrameRequest(BaseModel):
    filename: str
    subfolder: str = "video"
    type: str = "output"
    path: str | None = None
    position: str = "last"
    outputName: str | None = None
    offsetBeforeEnd: float | None = None
    outputWidth: int | None = None
    outputHeight: int | None = None


class ConcatRequest(BaseModel):
    files: list[str]
    inputDir: str | None = None
    output: str = Field(default_factory=lambda: "final.mp4")
    fade: float = 0.2
    fps: int = 24
    frames: int = 121
    noFade: bool = False
    chainTrim: bool = False
    smartSplice: bool = False
    splicePlan: Any = None
    trimHeadFrames: int | None = None
    trimTailFrames: int | None = None
    tailSec: float | None = None
    headSec: float | None = None
    audioCrossfadeSec: float | None = None
    microVideoFadeSec: float | None = None
    outputWidth: int | None = None
    outputHeight: int | None = None
    seamInterp: bool = False
    seamInterpFrames: int | None = None


class AnalyzeSpliceRequest(BaseModel):
    files: list[str]
    inputDir: str | None = None
    fps: int = 24
    tailSec: float | None = None
    headSec: float | None = None
    headMaxSec: float | None = None
    motionSearchWindow: int | None = None


class ValidateSegmentRequest(BaseModel):
    filename: str
    subfolder: str = "video"
    type: str = "output"
    path: str | None = None
    expectedWidth: int | None = None
    expectedHeight: int | None = None
    minDuration: float | None = None
    maxDuration: float | None = None
    requireAudio: bool = False
    expectedFrames: int | None = None
    expectedFps: float | None = None
    # 阶段二：ArcFace 身份质检（提供 referenceImageName 时默认开启）
    referenceImageName: str | None = None
    identityThreshold: float | None = Field(default=None, ge=0.0, le=1.0)
    checkIdentity: bool | None = None
    identityMaxFrames: int | None = Field(default=None, ge=1, le=30)


class DetectFaceRequest(BaseModel):
    """无脸门控：检查 input/ 下某张条件图是否含人脸。"""

    imageName: str | None = None
    filename: str | None = None
    subfolder: str = ""
    type: str = "input"
    path: str | None = None


class LookbookRequest(BaseModel):
    """InstantID 定妆照 / 段首帧生产。"""

    face_image_name: str
    prompt: str
    negative_prompt: str = ""
    seed: int | None = None
    width: int | None = None
    height: int | None = None
    steps: int | None = None
    cfg: float | None = None
    filename_prefix: str | None = None


class NormalizeSegmentRequest(BaseModel):
    filename: str
    subfolder: str = "video"
    type: str = "output"
    path: str | None = None
    expectedFrames: int = 81
    fps: float = 16
    maxDuration: float | None = None
    outputName: str | None = None


class ValidateFinalRequest(BaseModel):
    filename: str | None = None
    output: str | None = None
    inputDir: str | None = None
    path: str | None = None
    expectedWidth: int | None = None
    expectedHeight: int | None = None
    minDuration: float | None = None
    maxDuration: float | None = None
    requireAudio: bool = True


class AnimateRelockRequest(BaseModel):
    """阶段四（可选）：Wan2.2-Animate 关键镜头身份锁定重渲染。"""

    filename: str
    subfolder: str = "video"
    type: str = "output"
    path: str | None = None
    referenceImageName: str
    seed: int | None = None
    output: str | None = None


class DubMediaRef(BaseModel):
    filename: str
    subfolder: str = "video"
    type: str = "output"
    path: str | None = None


class DubCharacter(BaseModel):
    id: str
    name: str
    voiceId: str = ""
    speakerId: str | None = None
    referenceImageName: str | None = None
    faceTrackId: str | None = None
    bindingThreshold: float | None = Field(default=None, ge=-1.0, le=1.0)


class DubUtterance(BaseModel):
    id: str
    speakerId: str
    text: str = Field(min_length=1)
    startFrame: int = Field(ge=0)
    endFrame: int = Field(gt=0)
    lipSyncPolicy: Literal["off", "preferred", "required"] = "off"
    faceTrackId: str | None = None
    shotIndex: int | None = None


class DubDialogue(BaseModel):
    shotIndex: int
    shotName: str | None = None
    text: str = ""
    startFrame: int | None = None
    endFrame: int | None = None
    lipSyncPolicy: Literal["off", "preferred", "required"] = "off"


class DubRequest(BaseModel):
    """25fps visual-master dubbing pipeline request."""

    media: DubMediaRef | None = None
    splicePlan: Any = None
    timelineMap: list[dict[str, Any]] | None = None
    characters: list[DubCharacter] = Field(default_factory=list)
    dialogues: list[DubDialogue] | None = None
    utterances: list[DubUtterance] | None = None
    faceBindingMode: Literal["auto", "manual", "off"] = "auto"
    bindingOverrides: dict[str, str] = Field(default_factory=dict)
    sampleRate: Literal[48000] = 48000

    # Legacy contract retained for compatibility.
    filename: str | None = None
    inputDir: str | None = None
    path: str | None = None
    output: str | None = None
    segments: list[dict[str, Any]] | None = None
    fps: Literal[25] = 25
    ttsMode: Literal["required", "preferred"] | None = None
    lipsyncMode: Literal["required", "preferred"] | None = None


class DubAnalyzeRequest(BaseModel):
    media: DubMediaRef
    characters: list[DubCharacter] = Field(default_factory=list)
    faceBindingMode: Literal["auto", "manual", "off"] = "auto"


class DubRenderRequest(BaseModel):
    sessionId: str
    characters: list[DubCharacter] = Field(default_factory=list)
    utterances: list[DubUtterance]
    bindingOverrides: dict[str, str] = Field(default_factory=dict)
    output: str | None = None
    sampleRate: Literal[48000] = 48000


class DetectDuplicatesRequest(BaseModel):
    filename: str | None = None
    subfolder: str = "video"
    type: str = "output"
    path: str | None = None
    ssimThreshold: float | None = None
    minFrames: int | None = None
    sampleFps: float | None = None


class CharacterUpsertRequest(BaseModel):
    id: str
    name: str
    character: dict[str, Any] | None = None
