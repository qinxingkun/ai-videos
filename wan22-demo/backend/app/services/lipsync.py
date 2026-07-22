from __future__ import annotations

import asyncio
import json
import shlex
import shutil
import tempfile
import uuid
from pathlib import Path

try:
    import numpy as np
except ImportError:  # Optional until target-face processing is requested.
    np = None

from app.services.http_client import async_client

from app.config import Settings
from app.services.dubbing_timeline import DubbingTimeline, TimelineItem
from app.services.media_probe import probe_media
from app.services.tts_provider import ProviderUnavailable


class LatentSyncProvider:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.degraded = False
        self.name = "latentsync-http" if settings.latentsync_url else "latentsync-cli"

    async def apply(
        self,
        video: Path,
        audio: Path,
        output: Path,
        *,
        face_track: dict | None = None,
    ) -> None:
        if self.settings.latentsync_url:
            async with async_client(timeout=self.settings.provider_timeout_sec) as client:
                with video.open("rb") as vf, audio.open("rb") as af:
                    files = {"video": (video.name, vf), "audio": (audio.name, af)}
                    data = {
                        "request_id": uuid.uuid4().hex,
                        "seed": "1247",
                    }
                    if face_track:
                        data["face_track"] = json.dumps(face_track)
                    response = await client.post(
                        self.settings.latentsync_url,
                        files=files,
                        data=data,
                    )
                response.raise_for_status()
                output.write_bytes(response.content)
            return
        if not self.settings.latentsync_cli:
            raise ProviderUnavailable("LatentSync is not configured")
        values = {"video": str(video), "audio": str(audio), "output": str(output)}
        args = [part.format_map(values) for part in shlex.split(self.settings.latentsync_cli)]
        process = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode:
            raise RuntimeError((stderr or stdout).decode(errors="replace")[-800:])


class PassthroughLipSyncProvider:
    name = "passthrough-fallback"
    degraded = True

    async def apply(
        self,
        video: Path,
        audio: Path,
        output: Path,
        *,
        face_track: dict | None = None,
    ) -> None:
        await asyncio.to_thread(shutil.copyfile, video, output)


def create_lipsync_provider(settings: Settings):
    if settings.latentsync_url or settings.latentsync_cli:
        return LatentSyncProvider(settings)
    if settings.lipsync_provider_mode == "preferred":
        return PassthroughLipSyncProvider()
    raise ProviderUnavailable("LatentSync provider is required but neither HTTP nor CLI is configured")


async def _run(args: list[str]) -> None:
    process = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    if process.returncode:
        raise RuntimeError((stderr or stdout).decode(errors="replace")[-1000:])


async def _extract_inputs(
    master: Path,
    audio: Path,
    item: TimelineItem,
    video_out: Path,
    audio_out: Path,
    *,
    fps: float,
) -> None:
    frames = item.end_frame - item.start_frame
    await _run(
        [
            "ffmpeg", "-y", "-i", str(master), "-an",
            "-vf",
            f"trim=start_frame={item.start_frame}:end_frame={item.end_frame},"
            f"setpts=PTS-STARTPTS,fps={fps}",
            "-frames:v", str(frames), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video_out),
        ]
    )
    await _run(
        [
            "ffmpeg", "-y", "-i", str(audio), "-vn",
            "-af",
            f"atrim=start_sample={item.start_sample}:end_sample={item.end_sample},"
            "asetpts=PTS-STARTPTS,aresample=16000",
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(audio_out),
        ]
    )


def _track_boxes_for_item(
    item: TimelineItem,
    track: dict,
    *,
    visible_ratio_min: float,
) -> list[list[float]]:
    by_frame = {
        int(observation["frameIndex"]): [float(v) for v in observation["bbox"]]
        for observation in track.get("observations") or []
    }
    frames = list(range(item.start_frame, item.end_frame))
    visible = sum(frame in by_frame for frame in frames)
    ratio = visible / max(1, len(frames))
    if ratio < visible_ratio_min:
        raise RuntimeError(
            f"face track {track.get('id')} visible ratio {ratio:.3f} < {visible_ratio_min:.3f}"
        )
    known = sorted(by_frame)
    boxes: list[list[float]] = []
    for frame in frames:
        if frame in by_frame:
            boxes.append(by_frame[frame])
            continue
        before = max((value for value in known if value < frame), default=None)
        after = min((value for value in known if value > frame), default=None)
        if before is None and after is None:
            raise RuntimeError(f"face track {track.get('id')} has no observations")
        if before is None:
            boxes.append(by_frame[after])
        elif after is None:
            boxes.append(by_frame[before])
        else:
            weight = (frame - before) / (after - before)
            boxes.append(
                [
                    by_frame[before][index] * (1 - weight) + by_frame[after][index] * weight
                    for index in range(4)
                ]
            )
    return boxes


def _expanded_square(box: list[float], width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = box
    center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
    size = max(x2 - x1, y2 - y1) * 1.8
    center_y += size * 0.08
    left = max(0, int(round(center_x - size / 2)))
    top = max(0, int(round(center_y - size / 2)))
    right = min(width, int(round(center_x + size / 2)))
    bottom = min(height, int(round(center_y + size / 2)))
    return left, top, right, bottom


def _extract_track_roi(
    master: Path,
    item: TimelineItem,
    boxes: list[list[float]],
    output: Path,
    *,
    fps: float,
) -> list[tuple[int, int, int, int]]:
    import cv2

    capture = cv2.VideoCapture(str(master))
    if not capture.isOpened():
        raise RuntimeError("cannot open visual master for track crop")
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    writer = cv2.VideoWriter(
        str(output),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (512, 512),
    )
    if not writer.isOpened():
        capture.release()
        raise RuntimeError("cannot create face-track ROI video")
    regions: list[tuple[int, int, int, int]] = []
    try:
        capture.set(cv2.CAP_PROP_POS_FRAMES, item.start_frame)
        for box in boxes:
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError("visual master ended while extracting face track")
            region = _expanded_square(box, width, height)
            left, top, right, bottom = region
            crop = frame[top:bottom, left:right]
            if crop.size == 0:
                raise RuntimeError("face-track ROI is empty")
            writer.write(cv2.resize(crop, (512, 512), interpolation=cv2.INTER_LANCZOS4))
            regions.append(region)
    finally:
        writer.release()
        capture.release()
    return regions


def _feather_mask(width: int, height: int) -> np.ndarray:
    import cv2

    mask = np.zeros((height, width), dtype="float32")
    center = (width // 2, int(height * 0.58))
    axes = (max(1, int(width * 0.31)), max(1, int(height * 0.37)))
    cv2.ellipse(mask, center, axes, 0, 0, 360, 1.0, -1)
    sigma = max(3, min(width, height) // 18)
    return cv2.GaussianBlur(mask, (0, 0), sigma)[..., None]


def _composite_track_roi(
    master: Path,
    synced_roi: Path,
    item: TimelineItem,
    regions: list[tuple[int, int, int, int]],
    output: Path,
    *,
    fps: float,
) -> None:
    import cv2

    source = cv2.VideoCapture(str(master))
    synced = cv2.VideoCapture(str(synced_roi))
    if not source.isOpened() or not synced.isOpened():
        source.release()
        synced.release()
        raise RuntimeError("cannot open ROI composition inputs")
    width = int(source.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(source.get(cv2.CAP_PROP_FRAME_HEIGHT))
    writer = cv2.VideoWriter(
        str(output),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        source.release()
        synced.release()
        raise RuntimeError("cannot create composed LatentSync clip")
    try:
        source.set(cv2.CAP_PROP_POS_FRAMES, item.start_frame)
        for region in regions:
            ok_source, frame = source.read()
            ok_synced, generated = synced.read()
            if not ok_source or not ok_synced:
                raise RuntimeError("LatentSync ROI frame count changed during composition")
            left, top, right, bottom = region
            target_width, target_height = right - left, bottom - top
            patch = cv2.resize(generated, (target_width, target_height), interpolation=cv2.INTER_LANCZOS4)
            original = frame[top:bottom, left:right].astype("float32")
            mask = _feather_mask(target_width, target_height)
            frame[top:bottom, left:right] = np.clip(
                patch.astype("float32") * mask + original * (1 - mask), 0, 255
            ).astype("uint8")
            writer.write(frame)
    finally:
        writer.release()
        source.release()
        synced.release()
def _validate_synced_clip(path: Path, *, expected_frames: int, fps: float) -> None:
    probe = probe_media(path)
    actual_fps = probe["fps"]
    stream = probe["videoStreams"][0] if probe["videoStreams"] else {}
    actual_frames = stream.get("nb_frames")
    if actual_frames is None:
        actual_frames = round(probe["duration"] * fps)
    if actual_fps is None or abs(actual_fps - fps) > 0.01:
        raise RuntimeError(f"LatentSync output fps {actual_fps} != {fps}")
    if actual_frames != expected_frames:
        raise RuntimeError(f"LatentSync output frames {actual_frames} != {expected_frames}")
    if abs(probe["duration"] - expected_frames / fps) > 1 / fps:
        raise RuntimeError("LatentSync output duration differs by more than one frame")


async def _reassemble(
    master: Path,
    replacements: list[tuple[TimelineItem, Path]],
    output: Path,
    *,
    total_frames: int,
    fps: float,
) -> None:
    if not replacements:
        await asyncio.to_thread(shutil.copyfile, master, output)
        return
    args = ["ffmpeg", "-y", "-i", str(master)]
    for _, path in replacements:
        args += ["-i", str(path)]
    filters: list[str] = []
    labels: list[str] = []
    cursor = 0
    part = 0
    for input_index, (item, _) in enumerate(replacements, start=1):
        if item.start_frame > cursor:
            label = f"part{part}"
            filters.append(
                f"[0:v]trim=start_frame={cursor}:end_frame={item.start_frame},"
                f"setpts=PTS-STARTPTS[{label}]"
            )
            labels.append(f"[{label}]")
            part += 1
        label = f"part{part}"
        filters.append(
            f"[{input_index}:v]trim=start_frame=0:end_frame={item.end_frame - item.start_frame},"
            f"setpts=PTS-STARTPTS,fps={fps}[{label}]"
        )
        labels.append(f"[{label}]")
        part += 1
        cursor = item.end_frame
    if cursor < total_frames:
        label = f"part{part}"
        filters.append(
            f"[0:v]trim=start_frame={cursor}:end_frame={total_frames},setpts=PTS-STARTPTS[{label}]"
        )
        labels.append(f"[{label}]")
    filters.append(f"{''.join(labels)}concat=n={len(labels)}:v=1:a=0,setpts=PTS-STARTPTS[out]")
    await _run(
        args
        + [
            "-filter_complex", ";".join(filters), "-map", "[out]",
            "-frames:v", str(total_frames), "-r", str(fps), "-fps_mode", "cfr",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output),
        ]
    )


async def apply_selective_lipsync(
    master: Path,
    audio: Path,
    output: Path,
    *,
    timeline: DubbingTimeline,
    provider,
    visual_degraded: bool,
    face_atlas: dict | None = None,
) -> dict:
    required = [item for item in timeline.items if item.lip_sync_policy == "required"]
    if required and visual_degraded:
        raise RuntimeError("required lip sync cannot run on degraded visual master")
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="selective-lipsync-"))
    replacements: list[tuple[TimelineItem, Path]] = []
    fallbacks: list[dict] = []
    bindings: list[dict] = []
    tracks = {
        track["id"]: track for track in (face_atlas or {}).get("tracks") or []
    }
    visible_ratio_min = getattr(
        getattr(provider, "settings", None),
        "face_visible_ratio_min",
        0.65,
    )
    try:
        for item in timeline.items:
            policy = item.lip_sync_policy
            if policy == "off":
                continue
            if provider is None or getattr(provider, "degraded", False):
                if policy == "required":
                    raise ProviderUnavailable("required LatentSync provider is not configured")
                fallbacks.append({"dialogueIndex": item.index, "reason": "LatentSync unavailable"})
                continue
            clip = tmp / f"clip_{item.index}.mp4"
            pcm16 = tmp / f"audio_{item.index}_16k.wav"
            synced = tmp / f"synced_{item.index}.mp4"
            composed = tmp / f"composed_{item.index}.mp4"
            try:
                await _extract_inputs(master, audio, item, clip, pcm16, fps=timeline.fps)
                provider_input = clip
                regions = None
                track = tracks.get(item.face_track_id) if item.face_track_id else None
                if face_atlas is not None:
                    if track is None:
                        raise RuntimeError(
                            f"faceTrackId is required for speaker {item.speaker_id or item.speaker}"
                        )
                    boxes = _track_boxes_for_item(
                        item,
                        track,
                        visible_ratio_min=visible_ratio_min,
                    )
                    roi = tmp / f"roi_{item.index}.mp4"
                    regions = await asyncio.to_thread(
                        _extract_track_roi,
                        master,
                        item,
                        boxes,
                        roi,
                        fps=timeline.fps,
                    )
                    provider_input = roi
                face_track_payload = {
                        "trackId": item.face_track_id,
                        "utteranceId": item.utterance_id,
                    }
                if item.face_track_id:
                    await provider.apply(
                        provider_input,
                        pcm16,
                        synced,
                        face_track=face_track_payload,
                    )
                else:
                    await provider.apply(provider_input, pcm16, synced)
                _validate_synced_clip(
                    synced,
                    expected_frames=item.end_frame - item.start_frame,
                    fps=timeline.fps,
                )
                replacement = synced
                if regions is not None:
                    await asyncio.to_thread(
                        _composite_track_roi,
                        master,
                        synced,
                        item,
                        regions,
                        composed,
                        fps=timeline.fps,
                    )
                    _validate_synced_clip(
                        composed,
                        expected_frames=item.end_frame - item.start_frame,
                        fps=timeline.fps,
                    )
                    replacement = composed
                replacements.append((item, replacement))
                bindings.append(
                    {
                        "dialogueIndex": item.index,
                        "utteranceId": item.utterance_id,
                        "speakerId": item.speaker_id,
                        "faceTrackId": item.face_track_id,
                        "bindingConfidence": item.binding_confidence,
                    }
                )
            except Exception as exc:
                if policy == "required":
                    raise RuntimeError(f"required LatentSync failed: {exc}") from exc
                fallbacks.append({"dialogueIndex": item.index, "reason": str(exc)})
        await _reassemble(
            master,
            replacements,
            output,
            total_frames=timeline.total_frames,
            fps=timeline.fps,
        )
        probe = probe_media(output)
        frames = (probe["videoStreams"][0] if probe["videoStreams"] else {}).get("nb_frames")
        if frames is not None and frames != timeline.total_frames:
            raise RuntimeError(f"reassembled frames {frames} != master {timeline.total_frames}")
        return {
            "appliedCount": len(replacements),
            "fallbacks": fallbacks,
            "degraded": bool(fallbacks),
            "bindings": bindings,
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
