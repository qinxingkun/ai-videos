from __future__ import annotations

import json
import os
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _rate(value: Any) -> float | None:
    if not value or value in {"0/0", "N/A"}:
        return None
    try:
        rate = float(Fraction(str(value)))
        return rate if rate > 0 else None
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _stream_info(stream: dict[str, Any]) -> dict[str, Any]:
    info = {
        "index": _int(stream.get("index")),
        "codec_type": stream.get("codec_type"),
        "codec_name": stream.get("codec_name"),
        "profile": stream.get("profile"),
        "time_base": stream.get("time_base"),
        "start_pts": _int(stream.get("start_pts")),
        "start_time": _float(stream.get("start_time")),
        "duration": _float(stream.get("duration")),
    }
    if stream.get("codec_type") == "video":
        info.update(
            {
                "width": _int(stream.get("width")) or 0,
                "height": _int(stream.get("height")) or 0,
                "pix_fmt": stream.get("pix_fmt"),
                "level": _int(stream.get("level")),
                "fps": _rate(stream.get("avg_frame_rate")) or _rate(stream.get("r_frame_rate")),
                "avg_frame_rate": stream.get("avg_frame_rate"),
                "r_frame_rate": stream.get("r_frame_rate"),
                "nb_frames": _int(stream.get("nb_frames")),
            }
        )
    elif stream.get("codec_type") == "audio":
        info.update(
            {
                "sample_rate": _int(stream.get("sample_rate")),
                "channels": _int(stream.get("channels")),
                "channel_layout": stream.get("channel_layout"),
            }
        )
    return info


def probe_media(path: str | Path) -> dict[str, Any]:
    path = str(path)
    r = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            (
                "stream=index,codec_type,codec_name,profile,width,height,pix_fmt,level,"
                "r_frame_rate,avg_frame_rate,nb_frames,time_base,start_pts,start_time,"
                "duration,sample_rate,channels,channel_layout"
            ),
            "-show_entries",
            "format=duration,format_name",
            "-of",
            "json",
            path,
        ],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise RuntimeError((r.stderr or "ffprobe failed")[-300:])
    data = json.loads(r.stdout or "{}")
    streams = [_stream_info(s) for s in data.get("streams") or []]
    video_streams = [s for s in streams if s["codec_type"] == "video"]
    audio_streams = [s for s in streams if s["codec_type"] == "audio"]
    stream = video_streams[0] if video_streams else {}
    fmt_dur = _float(data.get("format", {}).get("duration")) or 0.0
    duration = stream.get("duration")
    if duration is None:
        duration = fmt_dur

    return {
        # Existing top-level fields remain for compatibility.
        "width": int(stream.get("width") or 0),
        "height": int(stream.get("height") or 0),
        "duration": float(duration or 0),
        "fps": stream.get("fps"),
        "videoStreams": video_streams,
        "audioStreams": audio_streams,
        "streams": streams,
        "format": data.get("format") or {},
    }


def has_audio_stream(path: str | Path) -> bool:
    r = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=index",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    return r.returncode == 0 and bool((r.stdout or "").strip())


def _frame_count(probe: dict[str, Any]) -> int | None:
    streams = probe.get("videoStreams") or []
    for stream in streams:
        nb = stream.get("nb_frames")
        if nb is not None:
            return int(nb)
    fps = probe.get("fps")
    duration = probe.get("duration")
    if fps and duration:
        return max(1, round(float(duration) * float(fps)))
    return None


def _duration_issue_text(
    *,
    duration: float,
    bound: float,
    op: str,
    probe: dict[str, Any],
    expected_frames: int | None = None,
    expected_fps: float | None = None,
) -> str:
    nb = _frame_count(probe)
    fps = probe.get("fps")
    detail = f"duration {duration:.2f}s {op} {bound}s"
    extras: list[str] = []
    if nb is not None and fps:
        extras.append(f"≈{nb} frames @ {float(fps):.2f}fps")
    elif nb is not None:
        extras.append(f"≈{nb} frames")
    elif fps:
        extras.append(f"@ {float(fps):.2f}fps")
    if expected_frames is not None and expected_fps is not None:
        extras.append(f"expected {expected_frames}@{expected_fps:g}")
    if extras:
        detail = f"{detail}（{'；'.join(extras)}）"
    return detail


def is_duration_only_failure(issues: list[str] | None) -> bool:
    """True when every issue is a duration min/max breach (seed retry cannot fix)."""
    if not issues:
        return False
    return all(str(item).startswith("duration ") for item in issues)


def normalize_segment_duration(
    path: str | Path,
    output: str | Path,
    *,
    expected_frames: int,
    fps: float,
    max_duration: float | None = None,
) -> dict[str, Any]:
    """
    Re-encode to CFR at the expected fps and truncate to expected_frames when overlong.

    Handles both too-many-frames and wrong-fps metadata so segment QA can pass.
    """
    import subprocess

    source = Path(path)
    dest = Path(output)
    if expected_frames < 1 or fps <= 0:
        raise ValueError("expected_frames and fps must be positive")
    if not source.is_file():
        raise RuntimeError(f"Video not found: {source}")

    probe = probe_media(source)
    limit = max_duration if max_duration is not None else (expected_frames / fps) + 0.75
    if probe["duration"] <= limit:
        return {
            "applied": False,
            "path": str(source),
            "probe": probe,
            "reason": "already within max duration",
        }

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp.mp4")
    vf = f"fps={fps:g},setpts=PTS-STARTPTS"
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-vf",
        vf,
        "-frames:v",
        str(int(expected_frames)),
        "-r",
        f"{fps:g}",
        "-fps_mode",
        "cfr",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
    ]
    if has_audio_stream(source):
        cmd += ["-c:a", "aac", "-ar", "48000", "-ac", "2", "-shortest"]
    else:
        cmd += ["-an"]
    cmd.append(str(tmp))
    ran = subprocess.run(cmd, capture_output=True, text=True)
    if ran.returncode != 0 or not tmp.is_file():
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"normalize segment failed: {(ran.stderr or '')[-300:]}")
    os.replace(tmp, dest)
    out_probe = probe_media(dest)
    return {
        "applied": True,
        "path": str(dest),
        "sourcePath": str(source),
        "probeBefore": probe,
        "probe": out_probe,
        "expectedFrames": int(expected_frames),
        "fps": float(fps),
    }


def validate_segment(
    path: str | Path,
    *,
    width: int | None = None,
    height: int | None = None,
    min_dur: float | None = None,
    max_dur: float | None = None,
    require_audio: bool = False,
    expected_frames: int | None = None,
    expected_fps: float | None = None,
) -> dict[str, Any]:
    issues: list[str] = []
    if not path:
        return {"ok": False, "issues": ["missing path"]}
    try:
        probe = probe_media(path)
    except Exception as e:
        return {"ok": False, "issues": [str(e)]}

    if width and probe["width"] != width:
        issues.append(f"width {probe['width']} != {width}")
    if height and probe["height"] != height:
        issues.append(f"height {probe['height']} != {height}")
    if min_dur is not None and probe["duration"] < min_dur:
        issues.append(
            _duration_issue_text(
                duration=probe["duration"],
                bound=min_dur,
                op="<",
                probe=probe,
                expected_frames=expected_frames,
                expected_fps=expected_fps,
            )
        )
    if max_dur is not None and probe["duration"] > max_dur:
        issues.append(
            _duration_issue_text(
                duration=probe["duration"],
                bound=max_dur,
                op=">",
                probe=probe,
                expected_frames=expected_frames,
                expected_fps=expected_fps,
            )
        )
    has_audio = has_audio_stream(path)
    if require_audio and not has_audio:
        issues.append("no audio stream")
    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "probe": probe,
        "hasAudio": has_audio,
        "durationOnly": is_duration_only_failure(issues),
        "nbFrames": _frame_count(probe),
    }


def validate_final(
    path: str | Path,
    *,
    expected_width: int | None = None,
    expected_height: int | None = None,
    min_duration: float = 15,
    max_duration: float = 22,
    require_audio: bool = True,
) -> dict[str, Any]:
    video_path = Path(path)
    issues: list[str] = []
    size = video_path.stat().st_size if video_path.exists() else 0
    if size < 1000:
        issues.append("output file too small or empty")
    try:
        probe = probe_media(video_path)
    except Exception as e:
        return {"ok": False, "issues": [str(e)], "path": str(video_path)}

    if expected_width and probe["width"] != expected_width:
        issues.append(f"width {probe['width']} != {expected_width}")
    if expected_height and probe["height"] != expected_height:
        issues.append(f"height {probe['height']} != {expected_height}")
    if probe["duration"] < min_duration:
        issues.append(f"duration {probe['duration']:.2f}s too short")
    if probe["duration"] > max_duration:
        issues.append(f"duration {probe['duration']:.2f}s too long")
    has_audio = has_audio_stream(video_path)
    if require_audio and not has_audio:
        issues.append("no audio stream")
    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "probe": probe,
        "path": str(video_path),
        "hasAudio": has_audio,
    }
