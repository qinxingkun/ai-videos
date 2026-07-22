from __future__ import annotations

import asyncio
import difflib
import re
import shutil
import tempfile
from dataclasses import replace
from pathlib import Path

from app.services.http_client import async_client
from app.services.media_probe import probe_media
from app.services.dubbing_timeline import DubbingTimeline, frames_to_samples
from app.services.lipsync import _extract_track_roi, _track_boxes_for_item
from app.services.face_tracking import evaluate_track_preservation


async def _decode_pcm_samples(path: str | Path, *, sample_rate: int = 48_000, channels: int = 2) -> int:
    process = await asyncio.create_subprocess_exec(
        "ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0",
        "-f", "s16le", "-acodec", "pcm_s16le", "-ar", str(sample_rate), "-ac", str(channels), "-",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode:
        raise RuntimeError(stderr.decode(errors="replace")[-800:])
    return len(stdout) // (2 * channels)


async def _measure_loudness(path: str | Path) -> dict:
    process = await asyncio.create_subprocess_exec(
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
        "-map", "0:a:0", "-af", "ebur128=peak=true", "-f", "null", "-",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    text = stderr.decode(errors="replace")
    if process.returncode:
        raise RuntimeError(text[-800:])
    integrated = re.findall(r"\bI:\s*(-?\d+(?:\.\d+)?)\s+LUFS", text)
    peaks = re.findall(r"\bPeak:\s*(-?\d+(?:\.\d+)?)\s+dBFS", text)
    if not integrated or not peaks:
        raise RuntimeError("ebur128 summary not found")
    return {"integratedLufs": float(integrated[-1]), "truePeakDbfs": float(peaks[-1])}


async def _decode_compatibility(path: str | Path) -> None:
    process = await asyncio.create_subprocess_exec(
        "ffmpeg", "-v", "error", "-i", str(path), "-map", "0:v:0", "-map", "0:a:0",
        "-f", "null", "-",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode:
        raise RuntimeError(stderr.decode(errors="replace")[-800:])


def _normalized_transcript(text: str) -> str:
    return "".join(re.findall(r"[\w\u3400-\u9fff]+", text.lower()))


async def _check_asr(
    path: str | Path,
    url: str,
    expected_text: str,
    *,
    similarity_min: float = 0.70,
) -> dict:
    async with async_client(timeout=600.0) as client:
        with Path(path).open("rb") as media:
            response = await client.post(
                url, files={"audio": (Path(path).name, media, "video/mp4")}
            )
        response.raise_for_status()
    actual = str(response.json().get("text") or "")
    expected_norm = _normalized_transcript(expected_text)
    actual_norm = _normalized_transcript(actual)
    similarity = (
        difflib.SequenceMatcher(None, expected_norm, actual_norm).ratio()
        if expected_norm
        else 1.0
    )
    return {
        "ok": similarity >= similarity_min,
        "similarity": similarity,
        "threshold": similarity_min,
        "text": actual,
    }


async def _check_syncnet(
    path: str | Path,
    url: str,
    *,
    confidence_min: float = 3.0,
    offset_max_frames: int = 1,
) -> dict:
    async with async_client(timeout=900.0) as client:
        with Path(path).open("rb") as media:
            response = await client.post(
                url, files={"video": (Path(path).name, media, "video/mp4")}
            )
        response.raise_for_status()
    payload = response.json()
    offset = int(payload["offsetFrames"])
    confidence = float(payload["confidence"])
    return {
        "ok": abs(offset) <= offset_max_frames and confidence >= confidence_min,
        "offsetFrames": offset,
        "confidence": confidence,
        "confidenceThreshold": confidence_min,
        "offsetMaxFrames": offset_max_frames,
    }


async def _run(args: list[str]) -> None:
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode:
        raise RuntimeError(stderr.decode(errors="replace")[-800:])


async def validate_utterance_qa(
    path: str | Path,
    *,
    timeline: DubbingTimeline,
    face_atlas: dict | None,
    asr_qa_url: str | None,
    syncnet_qa_url: str | None,
    visible_ratio_min: float = 0.65,
    asr_similarity_min: float = 0.70,
    syncnet_confidence_min: float = 3.0,
    syncnet_offset_max_frames: int = 1,
    original_master: str | Path | None = None,
) -> dict:
    """Run content and target-face sync QA for every utterance."""
    tracks = {
        track["id"]: track for track in (face_atlas or {}).get("tracks") or []
    }
    reports: list[dict] = []
    issues: list[str] = []
    tmp = Path(tempfile.mkdtemp(prefix="utterance-qa-"))
    try:
        for item in timeline.items:
            report: dict = {
                "utteranceId": item.utterance_id,
                "speakerId": item.speaker_id,
                "faceTrackId": item.face_track_id,
                "policy": item.lip_sync_policy,
                "ok": True,
                "issues": [],
            }
            clip = tmp / f"utterance_{item.index}.mp4"
            await _run(
                [
                    "ffmpeg", "-y", "-i", str(path),
                    "-vf",
                    f"trim=start_frame={item.start_frame}:end_frame={item.end_frame},setpts=PTS-STARTPTS",
                    "-af",
                    f"atrim=start_sample={item.start_sample}:end_sample={item.end_sample},asetpts=PTS-STARTPTS",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "pcm_s16le", str(clip.with_suffix(".mkv")),
                ]
            )
            content_clip = clip.with_suffix(".mkv")
            if asr_qa_url:
                try:
                    report["contentQa"] = await _check_asr(
                        content_clip,
                        asr_qa_url,
                        item.text,
                        similarity_min=asr_similarity_min,
                    )
                    if not report["contentQa"]["ok"]:
                        report["issues"].append("ASR similarity below threshold")
                except Exception as exc:
                    report["issues"].append(f"ASR verification failed: {exc}")
            if item.lip_sync_policy != "off":
                track = tracks.get(item.face_track_id)
                if track is None:
                    report["issues"].append("target face track is missing")
                elif not syncnet_qa_url:
                    if item.lip_sync_policy == "required":
                        report["issues"].append("required SyncNet endpoint is missing")
                else:
                    try:
                        qa_item = item
                        syncnet_min_frames = 75
                        item_frames = item.end_frame - item.start_frame
                        if item_frames < syncnet_min_frames:
                            missing = syncnet_min_frames - item_frames
                            qa_start = max(0, item.start_frame - missing // 2)
                            qa_end = min(
                                timeline.total_frames,
                                qa_start + syncnet_min_frames,
                            )
                            qa_start = max(0, qa_end - syncnet_min_frames)
                            qa_item = replace(
                                item,
                                start_frame=qa_start,
                                end_frame=qa_end,
                                start_sample=frames_to_samples(
                                    qa_start,
                                    fps=timeline.fps,
                                    sample_rate=timeline.sample_rate,
                                ),
                                end_sample=frames_to_samples(
                                    qa_end,
                                    fps=timeline.fps,
                                    sample_rate=timeline.sample_rate,
                                ),
                            )
                        boxes = _track_boxes_for_item(
                            qa_item, track, visible_ratio_min=visible_ratio_min
                        )
                        roi_video = tmp / f"qa_roi_{item.index}.mp4"
                        await asyncio.to_thread(
                            _extract_track_roi,
                            Path(path),
                            qa_item,
                            boxes,
                            roi_video,
                            fps=timeline.fps,
                        )
                        qa_audio = tmp / f"qa_audio_{item.index}.wav"
                        await _run(
                            [
                                "ffmpeg", "-y", "-i", str(path), "-vn",
                                "-af",
                                f"atrim=start_sample={qa_item.start_sample}:"
                                f"end_sample={qa_item.end_sample},asetpts=PTS-STARTPTS",
                                "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le",
                                str(qa_audio),
                            ]
                        )
                        roi_muxed = tmp / f"qa_roi_{item.index}.mkv"
                        await _run(
                            [
                                "ffmpeg", "-y", "-i", str(roi_video),
                                "-i", str(qa_audio), "-map", "0:v:0", "-map", "1:a:0",
                                "-c:v", "copy", "-c:a", "pcm_s16le", str(roi_muxed),
                            ]
                        )
                        report["lipSyncQa"] = await _check_syncnet(
                            roi_muxed,
                            syncnet_qa_url,
                            confidence_min=syncnet_confidence_min,
                            offset_max_frames=syncnet_offset_max_frames,
                        )
                        if not report["lipSyncQa"]["ok"]:
                            report["issues"].append("target-face SyncNet gate failed")
                    except Exception as exc:
                        report["issues"].append(f"target-face SyncNet failed: {exc}")
                if track is not None and original_master:
                    preservation = await asyncio.to_thread(
                        evaluate_track_preservation,
                        original_master,
                        path,
                        start_frame=item.start_frame,
                        end_frame=item.end_frame,
                        track=track,
                    )
                    report["preservationQa"] = preservation
                    if not preservation["ok"]:
                        report["issues"].extend(preservation.get("issues") or [])
            report["ok"] = not report["issues"]
            if item.lip_sync_policy == "required" and not report["ok"]:
                issues.extend(
                    f"{item.utterance_id or item.index}: {issue}"
                    for issue in report["issues"]
                )
            reports.append(report)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {"ok": not issues, "issues": issues, "items": reports}


async def validate_dubbed_media(
    path: str | Path,
    *,
    expected_frames: int,
    expected_fps: float = 25,
    check_loudness: bool = True,
    expected_text: str = "",
    asr_qa_url: str | None = None,
    syncnet_qa_url: str | None = None,
    check_sync_qa: bool = False,
    require_sync_qa: bool = False,
    asr_similarity_min: float = 0.70,
    syncnet_confidence_min: float = 3.0,
    syncnet_offset_max_frames: int = 1,
) -> dict:
    probe = probe_media(path)
    issues: list[str] = []
    if probe["fps"] is None or abs(probe["fps"] - expected_fps) > 0.01:
        issues.append(f"video fps {probe['fps']} != {expected_fps}")
    videos = probe["videoStreams"]
    audios = probe["audioStreams"]
    if not videos:
        issues.append("missing video stream")
    else:
        if abs(videos[0].get("start_time") or 0) > 0.001 or (videos[0].get("start_pts") or 0) != 0:
            issues.append("video does not start at PTS 0")
        if videos[0].get("nb_frames") != expected_frames:
            issues.append(f"video frames {videos[0].get('nb_frames')} != master {expected_frames}")
    decoded_samples = None
    loudness = None
    content_qa: dict = {"ok": None, "skipped": True}
    lip_sync_qa: dict = {"ok": None, "skipped": True}
    if not audios:
        issues.append("missing audio stream")
    else:
        if abs(audios[0].get("start_time") or 0) > 0.001 or (audios[0].get("start_pts") or 0) != 0:
            issues.append("audio does not start at PTS 0")
        if audios[0].get("sample_rate") != 48_000:
            issues.append("audio sample rate is not 48000")
        try:
            decoded_samples = await _decode_pcm_samples(path)
            expected_samples = expected_frames * 48_000 // round(expected_fps)
            if abs(decoded_samples - expected_samples) > 48_000 / expected_fps:
                issues.append("decoded audio/video duration drift exceeds one frame")
        except Exception as exc:
            issues.append(f"audio decode verification failed: {exc}")
    if videos:
        video = videos[0]
        if video.get("codec_name") != "h264":
            issues.append(f"video codec {video.get('codec_name')} != h264")
        if video.get("pix_fmt") != "yuv420p":
            issues.append(f"video pixel format {video.get('pix_fmt')} != yuv420p")
    if audios and audios[0].get("codec_name") != "aac":
        issues.append(f"audio codec {audios[0].get('codec_name')} != aac")
    try:
        await _decode_compatibility(path)
    except Exception as exc:
        issues.append(f"full decode compatibility failed: {exc}")
    if audios and check_loudness:
        try:
            loudness = await _measure_loudness(path)
            if abs(loudness["integratedLufs"] - (-16.0)) > 1.0:
                issues.append("integrated loudness is outside -16±1 LUFS")
            if loudness["truePeakDbfs"] > -1.0:
                issues.append("true peak exceeds -1.0 dBFS")
        except Exception as exc:
            issues.append(f"loudness verification failed: {exc}")
    if expected_text and asr_qa_url:
        try:
            content_qa = await _check_asr(
                path,
                asr_qa_url,
                expected_text,
                similarity_min=asr_similarity_min,
            )
            if not content_qa["ok"]:
                issues.append("ASR dialogue similarity is below 0.70")
        except Exception as exc:
            content_qa = {"ok": False, "skipped": False, "error": str(exc)}
            issues.append(f"ASR dialogue verification failed: {exc}")
    if check_sync_qa:
        if not syncnet_qa_url and require_sync_qa:
            lip_sync_qa = {
                "ok": False,
                "skipped": True,
                "error": "SyncNet QA endpoint is not configured",
            }
            issues.append("required SyncNet QA endpoint is not configured")
        elif syncnet_qa_url:
            try:
                lip_sync_qa = await _check_syncnet(
                    path,
                    syncnet_qa_url,
                    confidence_min=syncnet_confidence_min,
                    offset_max_frames=syncnet_offset_max_frames,
                )
                if not lip_sync_qa["ok"]:
                    issues.append("SyncNet confidence/offset gate failed")
            except Exception as exc:
                lip_sync_qa = {"ok": False, "skipped": False, "error": str(exc)}
                issues.append(f"SyncNet verification failed: {exc}")
    return {
        "ok": not issues,
        "issues": issues,
        "probe": probe,
        "expectedFrames": expected_frames,
        "decodedPcmSamples": decoded_samples,
        "loudness": loudness,
        "compatibilityDecoded": not any("compatibility" in issue for issue in issues),
        "contentQa": content_qa,
        "lipSyncQa": lip_sync_qa,
    }
