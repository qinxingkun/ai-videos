from __future__ import annotations

import re
import time
import tempfile
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.services.animate_relock import generate_identity_relock
from app.services.concat_video import concat_videos
from app.services.duplicate_frames import detect_duplicate_frames as detect_dups
from app.services.media_probe import validate_final as probe_validate_final
from app.services.media_probe import validate_segment as probe_validate_segment
from app.services.media_probe import normalize_segment_duration as probe_normalize_segment
from app.services.media_probe import is_duration_only_failure
from app.services.splice_analysis import analyze_splice as analyze_splice_paths
from app.services.audio_fit import fit_audio
from app.services.audio_mix import loudnorm_two_pass, mix_pcm, mux_final
from app.services.av_qa import validate_dubbed_media, validate_utterance_qa
from app.services.dubbing_timeline import (
    build_dialogue_timeline,
    build_timeline,
    build_utterance_timeline,
)
from app.services.lipsync import LatentSyncProvider, apply_selective_lipsync
from app.services.media_probe import probe_media
from app.services.tts_provider import create_tts_provider
from app.services.visual_master import create_visual_master

OUTPUT_RES = {"width": 768, "height": 512}
SEGMENT_DURATION = {"min": 4.5, "max": 6.0}
FINAL_DURATION = {"min": 15, "max": 22}


def _estimated_speech_seconds(text: str) -> float:
    """Conservative preflight budget; real duration is still measured after TTS."""
    han = len(re.findall(r"[\u3400-\u9fff]", text))
    latin_words = len(re.findall(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*", text))
    pauses = len(re.findall(r"[,，;；:：.!。！？?]", text))
    return han / 6.0 + latin_words / 2.7 + pauses * 0.12


async def _synthesize_and_fit(tts, item, raw: Path, fit: Path) -> dict:
    target = item.duration_samples / 48_000
    estimate = _estimated_speech_seconds(item.text)
    if estimate > target * 1.5:
        raise RuntimeError(
            f"dialogue {item.index} exceeds text budget "
            f"({estimate:.2f}s estimated for {target:.2f}s slot); rewrite the line"
        )

    await tts.synthesize(item, raw, speed=1.0)
    measured = probe_media(raw)["duration"]
    requested_speed = 1.0
    if measured > target:
        requested_speed = min(1.05, measured / target)
        await tts.synthesize(item, raw, speed=requested_speed)

    result = await fit_audio(
        raw,
        fit,
        target_samples=item.duration_samples,
        max_speedup=1.05 / requested_speed,
    )
    return {
        **result,
        "estimatedDuration": estimate,
        "ttsSpeed": requested_speed,
        "totalSpeed": requested_speed * result["speed"],
    }


def resolve_video_path(
    settings: Settings,
    *,
    filename: str,
    subfolder: str = "video",
    type_: str = "output",
    path: str | None = None,
) -> Path:
    if path:
        return Path(path).resolve()
    if type_ == "output" and not subfolder:
        return settings.video_dir / filename.replace("video/", "", 1)
    base = settings.input_dir if type_ == "input" else settings.comfyui_root / type_ / (subfolder or "")
    return base / filename


def extract_frame_ffmpeg(
    video_path: Path,
    out_path: Path,
    *,
    position: str = "last",
    offset_before_end: float = 0.05,
    width: int | None = None,
    height: int | None = None,
) -> None:
    import subprocess

    from app.services.media_probe import probe_media

    vf: list[str] = []
    if width and height:
        vf.extend(["-vf", f"scale={width}:{height}:flags=lanczos"])

    def _run(cmd: list[str]) -> None:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 or not out_path.exists() or out_path.stat().st_size <= 0:
            raise RuntimeError((r.stderr or r.stdout or "ffmpeg extract failed")[-500:])

    # 新版 ffmpeg 写单张 jpg 需要 -update 1，否则可能提示 pattern 无效甚至写出空文件
    single_image = ["-update", "1", "-frames:v", "1", "-q:v", "2"]

    if position == "first":
        _run(["ffmpeg", "-y", "-i", str(video_path), *single_image, *vf, str(out_path)])
        return

    # 末帧：offset 过小会 seek 到最后一帧之后，导致空输出；至少留出约一帧的余量
    off = max(0.12, float(offset_before_end or 0.05))
    errors: list[str] = []

    # 1) 优先用 -sseof（相对片尾），对变长/短片更稳
    try:
        if out_path.exists():
            out_path.unlink()
        _run([
            "ffmpeg", "-y",
            "-sseof", f"-{off}",
            "-i", str(video_path),
            *vf, *single_image, str(out_path),
        ])
        return
    except Exception as exc:
        errors.append(f"sseof: {exc}")

    # 2) 回退：按 duration 计算 -ss
    try:
        if out_path.exists():
            out_path.unlink()
        dur = float(probe_media(video_path)["duration"])
        ss = max(0.0, dur - off)
        _run([
            "ffmpeg", "-y",
            "-ss", f"{ss:.4f}",
            "-i", str(video_path),
            *vf, *single_image, str(out_path),
        ])
        return
    except Exception as exc:
        errors.append(f"ss: {exc}")

    # 3) 最后手段：整段解码后 reverse 取首帧（慢但可靠）
    try:
        if out_path.exists():
            out_path.unlink()
        rev_vf = ["-vf", "reverse"]
        if width and height:
            rev_vf = ["-vf", f"scale={width}:{height}:flags=lanczos,reverse"]
        _run([
            "ffmpeg", "-y",
            "-i", str(video_path),
            *rev_vf,
            *single_image, str(out_path),
        ])
        return
    except Exception as exc:
        errors.append(f"reverse: {exc}")

    raise RuntimeError("ffmpeg extract last frame failed | " + " | ".join(errors)[-800:])


def extract_video_frame(body: dict[str, Any], settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    video_path = resolve_video_path(
        settings,
        filename=body.get("filename") or "",
        subfolder=body.get("subfolder", "video"),
        type_=body.get("type", "output"),
        path=body.get("path"),
    )
    if not video_path.exists():
        raise RuntimeError(f"Video not found: {video_path}")
    settings.input_dir.mkdir(parents=True, exist_ok=True)
    base = body.get("outputName") or f"chain_frame_{int(time.time() * 1000)}.jpg"
    out_path = settings.input_dir / base
    which = "first" if body.get("position") == "first" else "last"
    extract_frame_ffmpeg(
        video_path,
        out_path,
        position=which,
        offset_before_end=body.get("offsetBeforeEnd", 0.05),
        width=body.get("outputWidth") or body.get("width"),
        height=body.get("outputHeight") or body.get("height"),
    )
    return {"name": base, "path": str(out_path), "subfolder": "", "type": "input"}


def analyze_splice(body: dict[str, Any], settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    input_dir = Path(body.get("inputDir") or settings.video_dir)
    files = body.get("files") or []
    paths = [str(input_dir / f.replace("video/", "", 1)) for f in files]
    for p in paths:
        if not Path(p).exists():
            raise RuntimeError(f"Video not found: {p}")
    plan = analyze_splice_paths(
        paths,
        fps=body.get("fps", 24),
        tailSec=body.get("tailSec", 1.0),
        headSec=body.get("headSec", 1.0),
        headMaxSec=body.get("headMaxSec", 1.75),
        motionSearchWindow=body.get("motionSearchWindow"),
    )
    return {"plan": plan, "inputDir": str(input_dir)}


def _resolve_reference_image(settings: Settings, reference_image_name: str | None) -> Path | None:
    if not reference_image_name:
        return None
    return settings.input_dir / reference_image_name


def validate_segment(body: dict[str, Any], settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    video_path = resolve_video_path(
        settings,
        filename=body.get("filename") or "",
        subfolder=body.get("subfolder", "video"),
        type_=body.get("type", "output"),
        path=body.get("path"),
    )
    result = probe_validate_segment(
        video_path,
        width=body.get("expectedWidth", OUTPUT_RES["width"]),
        height=body.get("expectedHeight", OUTPUT_RES["height"]),
        min_dur=body.get("minDuration", SEGMENT_DURATION["min"]),
        max_dur=body.get("maxDuration", SEGMENT_DURATION["max"]),
        require_audio=body.get("requireAudio", False),
        expected_frames=body.get("expectedFrames"),
        expected_fps=body.get("expectedFps"),
    )
    result["durationOnly"] = is_duration_only_failure(result.get("issues"))

    # 阶段二：ArcFace 人脸一致性质检（可选；缺参考图/依赖时 skipped，不阻断）
    from app.services.character_qa import (  # noqa: PLC0415
        DEFAULT_IDENTITY_THRESHOLD,
        check_identity_similarity,
    )

    ref_name = body.get("referenceImageName") or body.get("reference_image_name")
    identity_enabled = body.get("checkIdentity")
    if identity_enabled is None:
        identity_enabled = bool(ref_name)
    identity: dict[str, Any] | None = None
    if identity_enabled and ref_name:
        ref_path = _resolve_reference_image(settings, ref_name)
        thr = body.get("identityThreshold")
        if thr is None:
            thr = body.get("identity_threshold")
        if thr is None:
            thr = DEFAULT_IDENTITY_THRESHOLD
        identity = check_identity_similarity(
            video_path,
            ref_path or Path(""),
            threshold=float(thr),
            max_frames=body.get("identityMaxFrames") or body.get("identity_max_frames"),
        )
        result["identity"] = identity
        if identity and not identity.get("skipped") and not identity.get("ok"):
            issues = list(result.get("issues") or [])
            for msg in identity.get("issues") or []:
                if msg not in issues:
                    issues.append(msg)
            result["issues"] = issues
            result["ok"] = False
            # 身份失败不是纯时长问题，允许自愈换 seed / 拉回定妆照
            result["durationOnly"] = False
    else:
        result["identity"] = {
            "ok": True,
            "skipped": True,
            "reason": "未提供 referenceImageName，跳过身份质检",
            "avgSimilarity": None,
            "minSimilarity": None,
            "issues": [],
        }

    return {"path": str(video_path), **result}


def normalize_segment(body: dict[str, Any], settings: Settings | None = None) -> dict:
    """Trim/retime an overlong segment to expected_frames @ fps before QA."""
    settings = settings or get_settings()
    video_path = resolve_video_path(
        settings,
        filename=body.get("filename") or "",
        subfolder=body.get("subfolder", "video"),
        type_=body.get("type", "output"),
        path=body.get("path"),
    )
    if not video_path.is_file():
        raise RuntimeError(f"Video not found: {video_path}")

    expected_frames = int(body.get("expectedFrames") or 81)
    fps = float(body.get("fps") or 16)
    max_duration = body.get("maxDuration")
    if max_duration is None:
        max_duration = SEGMENT_DURATION["max"]

    out_name = body.get("outputName")
    if not out_name:
        out_name = f"{video_path.stem}_norm{video_path.suffix or '.mp4'}"
    out_name = Path(out_name).name
    out_path = video_path.parent / out_name

    result = probe_normalize_segment(
        video_path,
        out_path,
        expected_frames=expected_frames,
        fps=fps,
        max_duration=float(max_duration),
    )
    subfolder = body.get("subfolder", "video")
    media_type = body.get("type", "output")
    if result.get("applied"):
        return {
            **result,
            "filename": out_name,
            "subfolder": subfolder,
            "type": media_type,
            "name": out_name,
        }
    return {
        **result,
        "filename": body.get("filename") or video_path.name,
        "subfolder": subfolder,
        "type": media_type,
        "name": body.get("filename") or video_path.name,
    }


def validate_final(body: dict[str, Any], settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    if body.get("path"):
        video_path = Path(body["path"]).resolve()
    else:
        video_path = Path(body.get("inputDir") or settings.video_dir) / (
            body.get("filename") or body.get("output") or ""
        )
    if not video_path.exists():
        raise RuntimeError(f"Final video not found: {video_path}")
    result = probe_validate_final(
        video_path,
        expected_width=body.get("expectedWidth"),
        expected_height=body.get("expectedHeight"),
        min_duration=body.get("minDuration", FINAL_DURATION["min"]),
        max_duration=body.get("maxDuration", FINAL_DURATION["max"]),
        require_audio=body.get("requireAudio", True),
    )
    return result


def detect_duplicate_frames(body: dict[str, Any], settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    if body.get("path"):
        video_path = Path(body["path"]).resolve()
    else:
        video_path = resolve_video_path(
            settings,
            filename=body.get("filename") or "",
            subfolder=body.get("subfolder", "video"),
            type_=body.get("type", "output"),
        )
    result = detect_dups(
        video_path,
        ssimThreshold=body.get("ssimThreshold"),
        minFrames=body.get("minFrames"),
        sampleFps=body.get("sampleFps"),
    )
    return {"path": str(video_path), **result}


def detect_face_gate(body: dict[str, Any], settings: Settings | None = None) -> dict:
    """无脸门控：检查条件图是否有人脸；供多分镜链式回退定妆照。"""
    from app.services.character_qa import detect_face_in_image  # noqa: PLC0415

    settings = settings or get_settings()
    if body.get("path"):
        image_path = Path(body["path"]).resolve()
    else:
        name = body.get("imageName") or body.get("filename") or ""
        if not name:
            raise RuntimeError("imageName or filename required")
        type_ = body.get("type") or "input"
        sub = (body.get("subfolder") or "").strip("/\\")
        base = settings.comfyui_root / type_
        image_path = (base / sub / Path(name).name) if sub else (base / Path(name).name)
    result = detect_face_in_image(image_path)
    return {"path": str(image_path), "imageName": image_path.name, **result}


def concat_segments(body: dict[str, Any], settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    files = body.get("files") or []
    if not files:
        raise RuntimeError("files required")
    output = body.get("output") or f"final_{int(time.time() * 1000)}.mp4"
    input_dir = Path(body.get("inputDir") or settings.video_dir)
    result = concat_videos(
        files,
        input_dir=input_dir,
        output=output,
        fps=body.get("fps", 24),
        frames=body.get("frames", 121),
        fade=body.get("fade", 0.2),
        no_fade=body.get("noFade", False),
        chain_trim=body.get("chainTrim", False),
        smart_splice=body.get("smartSplice", False),
        splice_plan=body.get("splicePlan"),
        trim_head_frames=body.get("trimHeadFrames", 24),
        trim_tail_frames=body.get("trimTailFrames", 24),
        head_sec=body.get("headSec", 1.0),
        tail_sec=body.get("tailSec", 1.0),
        audio_crossfade_sec=body.get("audioCrossfadeSec", 0.05),
        micro_video_fade_sec=body.get("microVideoFadeSec"),
        output_width=body.get("outputWidth", OUTPUT_RES["width"]),
        output_height=body.get("outputHeight", OUTPUT_RES["height"]),
        seam_interp=body.get("seamInterp", False),
        seam_interp_frames=body.get("seamInterpFrames") or 3,
    )
    out_path = Path(result["path"])
    return {
        "filename": out_path.name,
        "subfolder": "video",
        "type": "output",
        "path": str(out_path),
        "log": result.get("log", ""),
        "splicePlan": result.get("splicePlan") or body.get("splicePlan"),
        "seamInterpApplied": result.get("seamInterpApplied", False),
        "timelineMap": result.get("timelineMap"),
    }


def animate_relock(body: dict[str, Any], settings: Settings | None = None) -> dict:
    """阶段四（可选）：对单个关键分段做 Wan2.2-Animate 身份锁定重渲染。

    失败（自定义节点/模型未安装、ComfyUI 未启动、超时等）时返回 applied=False，
    并原样回传输入分段信息，调用方据此回退到第一遍生成的原始分段，不阻断主流程。
    """
    settings = settings or get_settings()
    video_path = resolve_video_path(
        settings,
        filename=body.get("filename") or "",
        subfolder=body.get("subfolder", "video"),
        type_=body.get("type", "output"),
        path=body.get("path"),
    )
    if not video_path.exists():
        raise RuntimeError(f"Video not found: {video_path}")
    ref_path = _resolve_reference_image(settings, body.get("referenceImageName"))
    if not ref_path or not ref_path.exists():
        raise RuntimeError("referenceImageName required and must exist for animate relock")

    out_name = body.get("output") or f"relock_{video_path.stem}_{int(time.time() * 1000)}.mp4"
    out_path = settings.video_dir / out_name
    applied = generate_identity_relock(
        video_path,
        ref_path,
        out_path=out_path,
        seed=body.get("seed"),
        settings=settings,
    )
    if not applied:
        return {
            "applied": False,
            "filename": video_path.name,
            "subfolder": "video",
            "type": "output",
            "path": str(video_path),
        }
    return {
        "applied": True,
        "filename": out_path.name,
        "subfolder": "video",
        "type": "output",
        "path": str(out_path),
    }


async def dub_media(body: dict[str, Any], settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    if body.get("ttsMode") or body.get("lipsyncMode"):
        settings = settings.model_copy(
            update={
                **({"tts_provider_mode": body["ttsMode"]} if body.get("ttsMode") else {}),
                **({"lipsync_provider_mode": body["lipsyncMode"]} if body.get("lipsyncMode") else {}),
            }
        )
    media = body.get("media") or {}
    source_path = media.get("path") or body.get("path")
    if source_path:
        source = Path(source_path).resolve()
    elif media:
        source = resolve_video_path(
            settings,
            filename=media.get("filename") or "",
            subfolder=media.get("subfolder", "video"),
            type_=media.get("type", "output"),
        )
    else:
        source = Path(body.get("inputDir") or settings.video_dir) / (body.get("filename") or "")
    if not source.exists():
        raise RuntimeError(f"Video not found: {source}")
    output_name = body.get("output") or f"dub_{source.stem}_{int(time.time() * 1000)}.mp4"
    output = Path(output_name) if Path(output_name).is_absolute() else settings.video_dir / output_name
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="media-dub-"))
    degradations: list[dict[str, str]] = []
    try:
        prepared_master = body.get("_visualMasterPath")
        visual_path = Path(prepared_master) if prepared_master else tmp / "visual_master.mp4"
        visual = (
            body.get("_visualMaster")
            if prepared_master
            else await create_visual_master(source, visual_path, settings=settings)
        )
        if not visual_path.is_file():
            raise RuntimeError(f"visual master not found: {visual_path}")
        if visual["degraded"]:
            degradations.append({"stage": "visualMaster", "reason": visual["degradationReason"]})
        requested_items = (
            body.get("utterances")
            if body.get("utterances") is not None
            else body.get("dialogues")
            if body.get("dialogues") is not None
            else body.get("segments") or []
        )
        if (
            settings.dub_required_rife
            and visual["degraded"]
            and any(item.get("lipSyncPolicy") == "required" for item in requested_items)
        ):
            raise RuntimeError("required dubbing requires a non-degraded RIFE visual master")
        visual_probe = probe_media(visual_path)
        video_stream = visual_probe["videoStreams"][0] if visual_probe["videoStreams"] else {}
        total_frames = video_stream.get("nb_frames")
        if total_frames is None:
            total_frames = round(visual_probe["duration"] * 25)
        if total_frames <= 0:
            raise RuntimeError("visual master has no decodable frames")

        if body.get("utterances") is not None:
            timeline = build_utterance_timeline(
                body.get("utterances") or [],
                characters=body.get("characters") or [],
                total_frames=total_frames,
                fps=25,
                sample_rate=48_000,
            )
        elif body.get("dialogues") is not None:
            timeline = build_dialogue_timeline(
                dialogues=body.get("dialogues") or [],
                timeline_map=body.get("timelineMap") or [],
                characters=body.get("characters") or [],
                total_frames=total_frames,
                fps=25,
                sample_rate=48_000,
            )
        else:
            legacy_segments = [
                {
                    **segment,
                    "lipSyncPolicy": segment.get(
                        "lipSyncPolicy", settings.lipsync_provider_mode
                    ),
                }
                for segment in body.get("segments") or []
            ]
            timeline = build_timeline(
                legacy_segments,
                fps=25,
                sample_rate=48_000,
                total_frames=total_frames,
            )

        tts = create_tts_provider(settings) if timeline.items else None
        if tts and tts.degraded:
            degradations.append({"stage": "tts", "reason": f"using {tts.name}"})
        fitted: list[Path] = []
        fit_reports: list[dict] = []
        for item in timeline.items:
            raw = tmp / f"tts_{item.index}.wav"
            fit = tmp / f"fit_{item.index}.wav"
            fit_reports.append(await _synthesize_and_fit(tts, item, raw, fit))
            fitted.append(fit)

        mixed = tmp / "timeline_pcm.wav"
        normalized = tmp / "normalized_pcm.wav"
        await mix_pcm(fitted, timeline, mixed)
        loudness = await loudnorm_two_pass(mixed, normalized)

        lipsync = (
            LatentSyncProvider(settings)
            if settings.latentsync_url or settings.latentsync_cli
            else None
        )
        synced = tmp / "lipsynced.mp4"
        lipsync_result = await apply_selective_lipsync(
            visual_path,
            normalized,
            synced,
            timeline=timeline,
            provider=lipsync,
            visual_degraded=visual["degraded"],
            face_atlas=body.get("_faceAtlas"),
        )
        if lipsync_result["degraded"]:
            degradations.append(
                {
                    "stage": "lipsync",
                    "reason": f"{len(lipsync_result['fallbacks'])} selective fallback(s)",
                }
            )
        await mux_final(synced, normalized, output)
        face_atlas = body.get("_faceAtlas")
        qa = await validate_dubbed_media(
            output,
            expected_frames=total_frames,
            check_loudness=bool(tts and not tts.degraded),
            expected_text=(
                " ".join(item.text for item in timeline.items)
                if tts and not tts.degraded and not face_atlas
                else None
            ),
            asr_qa_url=settings.asr_qa_url,
            syncnet_qa_url=settings.syncnet_qa_url,
            check_sync_qa=lipsync_result["appliedCount"] > 0 and not face_atlas,
            require_sync_qa=any(
                item.lip_sync_policy == "required" for item in timeline.items
            ),
            asr_similarity_min=settings.asr_qa_similarity_min,
            syncnet_confidence_min=settings.syncnet_confidence_min,
            syncnet_offset_max_frames=settings.syncnet_offset_max_frames,
        )
        if face_atlas and timeline.items:
            utterance_qa = await validate_utterance_qa(
                output,
                timeline=timeline,
                face_atlas=face_atlas,
                asr_qa_url=settings.asr_qa_url,
                syncnet_qa_url=settings.syncnet_qa_url,
                visible_ratio_min=settings.face_visible_ratio_min,
                asr_similarity_min=settings.asr_qa_similarity_min,
                syncnet_confidence_min=settings.syncnet_confidence_min,
                syncnet_offset_max_frames=settings.syncnet_offset_max_frames,
                original_master=visual_path,
            )
            qa["perUtteranceQa"] = utterance_qa
            if not utterance_qa["ok"]:
                qa["issues"].extend(utterance_qa["issues"])
                qa["ok"] = False
            preferred_failures = [
                item
                for item in utterance_qa["items"]
                if item["policy"] == "preferred" and not item["ok"]
            ]
            if preferred_failures:
                qa["initialPerUtteranceQa"] = utterance_qa
                degradations.append(
                    {
                        "stage": "utteranceQa",
                        "reason": f"{len(preferred_failures)} preferred utterance QA failure(s)",
                    }
                )
                failed_ids = {item["utteranceId"] for item in preferred_failures}
                fallback_timeline = replace(
                    timeline,
                    items=tuple(
                        replace(item, lip_sync_policy="off")
                        if item.utterance_id in failed_ids
                        else item
                        for item in timeline.items
                    ),
                )
                fallback_synced = tmp / "lipsynced_preferred_fallback.mp4"
                fallback_result = await apply_selective_lipsync(
                    visual_path,
                    normalized,
                    fallback_synced,
                    timeline=fallback_timeline,
                    provider=lipsync,
                    visual_degraded=visual["degraded"],
                    face_atlas=face_atlas,
                )
                for item in preferred_failures:
                    fallback_result["fallbacks"].append(
                        {
                            "utteranceId": item["utteranceId"],
                            "reason": "; ".join(item["issues"]),
                        }
                    )
                fallback_result["degraded"] = True
                lipsync_result = fallback_result
                await mux_final(fallback_synced, normalized, output)
                qa = await validate_dubbed_media(
                    output,
                    expected_frames=total_frames,
                    check_loudness=bool(tts and not tts.degraded),
                    asr_qa_url=settings.asr_qa_url,
                    syncnet_qa_url=settings.syncnet_qa_url,
                    check_sync_qa=False,
                    require_sync_qa=False,
                    asr_similarity_min=settings.asr_qa_similarity_min,
                    syncnet_confidence_min=settings.syncnet_confidence_min,
                    syncnet_offset_max_frames=settings.syncnet_offset_max_frames,
                )
                qa["initialPerUtteranceQa"] = utterance_qa
                qa["perUtteranceQa"] = await validate_utterance_qa(
                    output,
                    timeline=fallback_timeline,
                    face_atlas=face_atlas,
                    asr_qa_url=settings.asr_qa_url,
                    syncnet_qa_url=settings.syncnet_qa_url,
                    visible_ratio_min=settings.face_visible_ratio_min,
                    asr_similarity_min=settings.asr_qa_similarity_min,
                    syncnet_confidence_min=settings.syncnet_confidence_min,
                    syncnet_offset_max_frames=settings.syncnet_offset_max_frames,
                    original_master=visual_path,
                )
        if not qa["ok"]:
            raise RuntimeError("AV QA failed: " + "; ".join(qa["issues"]))
        output_media = {
            "filename": output.name,
            "subfolder": "video",
            "type": "output",
            "path": str(output),
        }
        return {
            "media": output_media,
            "path": str(output),
            "filename": output.name,
            "fps": 25,
            "degraded": bool(degradations),
            "degradations": degradations,
            "providers": {
                "tts": tts.name if tts else "none",
                "lipsync": lipsync.name if lipsync else "none",
            },
            "visualMaster": visual,
            "timeline": {
                "totalFrames": total_frames,
                "totalSamples": timeline.duration_samples,
                "items": len(timeline.items),
                "fitReports": fit_reports,
            },
            "lipSync": lipsync_result,
            "loudnormPass1": loudness,
            "qa": qa,
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def health_full(settings: Settings | None = None) -> dict:
    import subprocess

    import httpx

    settings = settings or get_settings()
    checks = []
    ffmpeg_ok = subprocess.run(["ffmpeg", "-version"], capture_output=True).returncode == 0
    checks.append({"name": "ffmpeg", "ok": ffmpeg_ok})
    ffprobe_ok = subprocess.run(["ffprobe", "-version"], capture_output=True).returncode == 0
    checks.append({"name": "ffprobe", "ok": ffprobe_ok})
    checks.append({"name": "video_dir", "ok": settings.video_dir.exists(), "path": str(settings.video_dir)})
    checks.append({"name": "input_dir", "ok": settings.input_dir.exists(), "path": str(settings.input_dir)})
    comfy_ok = False
    try:
        r = httpx.get(f"{settings.comfyui_url.rstrip('/')}/system_stats", timeout=5.0)
        comfy_ok = r.status_code == 200
    except Exception:
        comfy_ok = False
    checks.append({"name": "comfyui", "ok": comfy_ok, "url": settings.comfyui_url})
    provider_urls = {
        "cosyvoice": settings.cosyvoice_url,
        "latentsync": settings.latentsync_url,
        "asr_qa": settings.asr_qa_url,
        "syncnet_qa": settings.syncnet_qa_url,
    }
    from urllib.parse import urlsplit, urlunsplit

    checked_health_urls: dict[str, bool] = {}
    for name, url in provider_urls.items():
        if not url:
            checks.append({"name": name, "ok": True, "skipped": True})
            continue
        split = urlsplit(url)
        health_url = urlunsplit((split.scheme, split.netloc, "/health", "", ""))
        if health_url not in checked_health_urls:
            try:
                response = httpx.get(health_url, timeout=5.0)
                checked_health_urls[health_url] = response.status_code == 200
            except Exception:
                checked_health_urls[health_url] = False
        checks.append(
            {
                "name": name,
                "ok": checked_health_urls[health_url],
                "url": health_url,
            }
        )
    return {"ok": all(c["ok"] for c in checks), "checks": checks, "comfyuiRoot": str(settings.comfyui_root)}
