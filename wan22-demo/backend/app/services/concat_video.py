from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from app.services.media_probe import has_audio_stream, probe_media
from app.services.seam_interp import generate_seam_transition
from app.services.splice_analysis import analyze_splice


def _resolve_inputs(files: list[str], input_dir: Path) -> list[Path]:
    out: list[Path] = []
    for f in files:
        p = Path(f)
        if p.is_absolute():
            out.append(p)
            continue
        cand = input_dir / f
        if cand.exists():
            out.append(cand)
            continue
        alt = input_dir / f.replace("video/", "", 1)
        out.append(alt if alt.exists() else cand)
    return out


def _hard_concat(paths: list[Path], output: Path) -> None:
    list_file = output.parent / ".concat-list.txt"
    lines = []
    for p in paths:
        escaped = str(p).replace("'", r"'\''")
        lines.append(f"file '{escaped}'")
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        r = subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(output)],
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            raise RuntimeError(r.stderr or r.stdout or "hard concat failed")
    finally:
        list_file.unlink(missing_ok=True)


def _build_segment_windows(paths: list[Path], plan: dict, opts: dict) -> list[dict]:
    probes = [probe_media(p) for p in paths]
    joins = plan.get("joins") or []
    windows = []
    count = len(paths)
    for i in range(count):
        dur = probes[i]["duration"]
        start = 0.0
        end = dur
        if i > 0:
            prev = joins[i - 1] if i - 1 < len(joins) else {}
            head_cut = prev.get("headCutSec", opts["head_sec"])
            start = min(dur - 0.1, max(0.0, float(head_cut)))
        if i < count - 1:
            join = joins[i] if i < len(joins) else {}
            tail_cut = join.get("tailCutSec", opts["tail_sec"])
            end = max(start + 0.1, dur - min(float(tail_cut), dur - start - 0.05))
        windows.append(
            {
                "start": round(start, 6),
                "duration": round(max(0.1, end - start), 6),
                "probe": probes[i],
            }
        )
    return windows


def _build_timeline_map(
    windows: list[dict],
    *,
    fps: float,
    overlap_frames: int = 0,
    transition_frame_counts: list[int] | None = None,
    transition_frames: int | None = None,
) -> list[dict[str, Any]]:
    """Map each source trim window onto the output CFR frame timeline."""
    output_cursor = 0
    result: list[dict[str, Any]] = []
    # transition_frames was the old name for xfade overlap; preserve callers.
    overlap = max(0, int(transition_frames if transition_frames is not None else overlap_frames))
    inserted = transition_frame_counts or []
    for index, window in enumerate(windows):
        source_start = round(float(window["start"]) * fps)
        frame_count = max(1, round(float(window["duration"]) * fps))
        transition_before = 0
        if index:
            output_cursor -= overlap
            transition_before = inserted[index - 1] if index - 1 < len(inserted) else 0
            output_cursor += transition_before
        result.append(
            {
                "segmentIndex": index,
                "sourceStartSec": window["start"],
                "sourceDurationSec": window["duration"],
                "sourceStartFrame": source_start,
                "sourceEndFrame": source_start + frame_count,
                "outputStartFrame": output_cursor,
                "outputEndFrame": output_cursor + frame_count,
                "outputStartSec": output_cursor / fps,
                "outputEndSec": (output_cursor + frame_count) / fps,
                "transitionBeforeFrames": transition_before,
                "overlapBeforeFrames": overlap if index else 0,
            }
        )
        output_cursor += frame_count
    return result


def _build_smart_splice_filter(
    count: int,
    windows: list[dict],
    *,
    with_audio: bool,
    width: int,
    height: int,
    audio_crossfade_sec: float,
    audio_edge_fade_sec: float,
    micro_video_fade_sec: float,
    transition_input_indices: list[int] | None = None,
) -> tuple[str, str | None, str]:
    scale = f",scale={width}:{height}:flags=bicubic" if width and height else ""
    parts: list[str] = []
    v_labels: list[str] = []
    a_labels: list[str] = []

    for i in range(count):
        start = windows[i]["start"]
        duration = windows[i]["duration"]
        v_out = f"[v{i}t]"
        parts.append(
            f"[{i}:v]trim=start={start:.6f}:duration={duration:.6f},setpts=PTS-STARTPTS{scale}{v_out}"
        )
        v_labels.append(v_out)
        if with_audio:
            edge = min(audio_edge_fade_sec, duration / 4)
            fade_in = f",afade=t=in:st=0:d={edge:.4f}" if i > 0 else ""
            fade_out = (
                f",afade=t=out:st={max(0, duration - edge):.4f}:d={edge:.4f}" if i < count - 1 else ""
            )
            a_out = f"[a{i}t]"
            parts.append(
                f"[{i}:a]atrim=start={start:.6f}:duration={duration:.6f},asetpts=PTS-STARTPTS,"
                f"aresample=48000:first_pts=0{fade_in}{fade_out}{a_out}"
            )
            a_labels.append(a_out)

    video_label = "[vpre]"
    fade = max(0.0, float(micro_video_fade_sec or 0))
    if transition_input_indices and count > 1:
        # 接缝微观插帧（RIFE）：用真实插值过渡片段替代硬切/xfade，运动更连贯
        interleaved = [v_labels[0]]
        for i in range(1, count):
            t_idx = transition_input_indices[i - 1]
            t_out = f"[t{i - 1}v]"
            parts.append(f"[{t_idx}:v]setpts=PTS-STARTPTS{scale}{t_out}")
            interleaved.append(t_out)
            interleaved.append(v_labels[i])
        parts.append(f"{''.join(interleaved)}concat=n={len(interleaved)}:v=1[vpre]")
    elif fade > 0 and count > 1:
        prev = v_labels[0]
        offset = windows[0]["duration"] - fade
        for i in range(1, count):
            out = "[vpre]" if i == count - 1 else f"[vx{i}]"
            safe_offset = max(0.0, offset)
            parts.append(
                f"{prev}{v_labels[i]}xfade=transition=fade:duration={fade:.4f}:offset={safe_offset:.4f}{out}"
            )
            prev = out
            if i < count - 1:
                offset = safe_offset + windows[i]["duration"] - fade
    else:
        parts.append(f"{''.join(v_labels)}concat=n={count}:v=1[vpre]")

    if with_audio and count > 1 and audio_crossfade_sec > 0:
        prev_a = a_labels[0]
        for i in range(1, count):
            out = "[aout]" if i == count - 1 else f"[am{i}]"
            parts.append(f"{prev_a}{a_labels[i]}acrossfade=d={audio_crossfade_sec}:c1=tri:c2=tri{out}")
            prev_a = out
        return ";".join(parts), "[aout]", video_label

    if with_audio:
        parts.append(f"{''.join(a_labels)}concat=n={count}:v=0:a=1[aout]")
        return ";".join(parts), "[aout]", video_label

    return ";".join(parts), None, video_label


def _build_chain_trim_filter(
    count: int,
    *,
    fps: float,
    frames: int,
    trim_head_frames: int,
    trim_tail_frames: int,
    with_audio: bool,
    width: int,
    height: int,
) -> tuple[str, str | None, str]:
    seg_dur = frames / fps
    trim_head_sec = trim_head_frames / fps
    trim_tail_sec = trim_tail_frames / fps
    scale = f",scale={width}:{height}:flags=bicubic" if width and height else ""
    parts: list[str] = []
    v_labels: list[str] = []
    a_labels: list[str] = []
    for i in range(count):
        start = trim_head_sec if i > 0 else 0.0
        tail = trim_tail_sec if i < count - 1 else 0.0
        dur = max(0.1, seg_dur - start - tail)
        parts.append(
            f"[{i}:v]trim=start={start:.6f}:duration={dur:.6f},setpts=PTS-STARTPTS{scale}[v{i}t]"
        )
        v_labels.append(f"[v{i}t]")
        if with_audio:
            parts.append(
                f"[{i}:a]atrim=start={start:.6f}:duration={dur:.6f},asetpts=PTS-STARTPTS[a{i}t]"
            )
            a_labels.append(f"[a{i}t]")
    if with_audio:
        interleaved = []
        for i in range(count):
            interleaved.extend([v_labels[i], a_labels[i]])
        parts.append(f"{''.join(interleaved)}concat=n={count}:v=1:a=1[vout][aout]")
        return ";".join(parts), "[aout]", "[vout]"
    parts.append(f"{''.join(v_labels)}concat=n={count}:v=1[vout]")
    return ";".join(parts), None, "[vout]"


def _build_xfade_filter(count: int, *, segment_sec: float, fade: float) -> str:
    parts = []
    prev = "[0:v]"
    for i in range(1, count):
        out = "[vout]" if i == count - 1 else f"[v{i}]"
        offset = i * segment_sec - i * fade
        parts.append(f"{prev}[{i}:v]xfade=transition=fade:duration={fade}:offset={offset:.2f}{out}")
        prev = out
    return ";".join(parts)


def _build_audio_acrossfade(count: int, *, fade: float) -> str | None:
    if count < 2:
        return None
    parts = []
    prev = "[0:a]"
    for i in range(1, count):
        out = "[aout]" if i == count - 1 else f"[a{i}]"
        parts.append(f"{prev}[{i}:a]acrossfade=d={fade}:c1=tri:c2=tri{out}")
        prev = out
    return ";".join(parts)


def _extract_boundary_frame(path: Path, at_sec: float, out_path: Path, *, width: int, height: int) -> bool:
    vf = f"scale={width}:{height}:flags=lanczos" if width and height else None
    args = ["ffmpeg", "-y", "-ss", f"{max(0.0, at_sec):.6f}", "-i", str(path), "-frames:v", "1"]
    if vf:
        args += ["-vf", vf]
    args += [str(out_path)]
    r = subprocess.run(args, capture_output=True, text=True)
    return r.returncode == 0 and out_path.exists()


def _try_build_seam_transitions(
    paths: list[Path],
    windows: list[dict],
    *,
    fps: float,
    num_frames: int,
    width: int,
    height: int,
    tmp_dir: Path,
) -> list[Path] | None:
    """为每个接缝生成 RIFE 插值过渡片段；任一环节失败即返回 None（调用方需回退到 micro-xfade）。"""
    count = len(paths)
    if count < 2:
        return None
    clips: list[Path] = []
    epsilon = 0.02
    for i in range(count - 1):
        left_at = max(0.0, windows[i]["start"] + windows[i]["duration"] - epsilon)
        right_at = windows[i + 1]["start"]
        left_png = tmp_dir / f"seam_left_{i}.png"
        right_png = tmp_dir / f"seam_right_{i}.png"
        if not _extract_boundary_frame(paths[i], left_at, left_png, width=width, height=height):
            return None
        if not _extract_boundary_frame(paths[i + 1], right_at, right_png, width=width, height=height):
            return None
        clip_path = tmp_dir / f"seam_transition_{i}.mp4"
        ok = generate_seam_transition(
            left_png, right_png, out_clip=clip_path, fps=fps, num_frames=num_frames
        )
        if not ok:
            return None
        clips.append(clip_path)
    return clips


def _run_ffmpeg(args: list[str]) -> str:
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or f"ffmpeg exit {r.returncode}")[-800:])
    return (r.stdout or "") + (r.stderr or "")


def concat_videos(
    files: list[str],
    *,
    input_dir: str | Path,
    output: str,
    fps: float = 24,
    frames: int = 121,
    fade: float = 0.2,
    no_fade: bool = False,
    chain_trim: bool = False,
    smart_splice: bool = False,
    splice_plan: dict | None = None,
    trim_head_frames: int = 24,
    trim_tail_frames: int = 24,
    head_sec: float = 1.0,
    tail_sec: float = 1.0,
    head_max_sec: float = 1.75,
    audio_crossfade_sec: float = 0.05,
    audio_edge_fade_sec: float = 0.03,
    micro_video_fade_sec: float | None = None,
    output_width: int = 768,
    output_height: int = 512,
    loudnorm: bool = True,
    crf: int = 19,
    seam_interp: bool = False,
    seam_interp_frames: int = 3,
) -> dict[str, Any]:
    input_dir = Path(input_dir)
    paths = _resolve_inputs(files, input_dir)
    for p in paths:
        if not p.exists():
            raise RuntimeError(f"file not found: {p}")

    out_path = Path(output) if Path(output).is_absolute() else input_dir / output
    segment_sec = frames / fps
    with_audio = all(has_audio_stream(p) for p in paths)
    logs: list[str] = []

    if smart_splice:
        # Two real output frames, independent of source model defaults.
        actual_micro_fade = 2 / fps if micro_video_fade_sec is None else micro_video_fade_sec
        plan = splice_plan or analyze_splice(
            [str(p) for p in paths],
            fps=fps,
            tailSec=tail_sec,
            headSec=head_sec,
            headMaxSec=head_max_sec,
        )
        windows = _build_segment_windows(
            paths, plan, {"head_sec": head_sec, "tail_sec": tail_sec}
        )

        transition_paths: list[Path] | None = None
        transition_frame_counts: list[int] = []
        seam_tmp: Path | None = None
        if seam_interp:
            seam_tmp = Path(tempfile.mkdtemp(prefix="seam-interp-"))
            try:
                transition_paths = _try_build_seam_transitions(
                    paths,
                    windows,
                    fps=fps,
                    num_frames=seam_interp_frames,
                    width=output_width,
                    height=output_height,
                    tmp_dir=seam_tmp,
                )
            except Exception:
                transition_paths = None
            logs.append(
                "seam-interp: 已生成 RIFE 过渡片段" if transition_paths else "seam-interp: 生成失败，回退到 micro-xfade"
            )
            if transition_paths:
                transition_frame_counts = [
                    probe_media(path)["videoStreams"][0].get("nb_frames")
                    or round(probe_media(path)["duration"] * fps)
                    for path in transition_paths
                ]

        try:
            transition_input_indices = (
                list(range(len(paths), len(paths) + len(transition_paths))) if transition_paths else None
            )
            filt, map_audio, video_label = _build_smart_splice_filter(
                len(paths),
                windows,
                with_audio=with_audio,
                width=output_width,
                height=output_height,
                audio_crossfade_sec=audio_crossfade_sec if with_audio else 0,
                audio_edge_fade_sec=audio_edge_fade_sec,
                micro_video_fade_sec=actual_micro_fade,
                transition_input_indices=transition_input_indices,
            )
            filter_complex = filt
            final_audio = map_audio
            if loudnorm and with_audio and map_audio:
                filter_complex += f";{map_audio}loudnorm=I=-16:TP=-1.5:LRA=11[aoutn]"
                final_audio = "[aoutn]"
            args = ["ffmpeg", "-y"]
            for p in paths:
                args += ["-i", str(p)]
            if transition_paths:
                for tp in transition_paths:
                    args += ["-i", str(tp)]
            args += ["-filter_complex", filter_complex, "-map", video_label]
            if final_audio:
                # Intermediate splice masters stay lossless. AAC is encoded only
                # once by the final delivery mux.
                args += ["-map", final_audio, "-c:a", "alac"]
            args += [
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                str(crf),
                "-pix_fmt",
                "yuv420p",
                str(out_path),
            ]
            logs.append(_run_ffmpeg(args))
        finally:
            if seam_tmp is not None:
                shutil.rmtree(seam_tmp, ignore_errors=True)
        return {
            "path": str(out_path),
            "filename": out_path.name,
            "splicePlan": plan,
            "log": "\n".join(logs),
            "seamInterpApplied": bool(transition_paths),
            "timelineMap": _build_timeline_map(
                windows,
                fps=fps,
                overlap_frames=(
                    0 if transition_paths else round(max(0.0, float(actual_micro_fade)) * fps)
                ),
                transition_frame_counts=transition_frame_counts,
            ),
        }

    if chain_trim:
        filt, map_audio, video_label = _build_chain_trim_filter(
            len(paths),
            fps=fps,
            frames=frames,
            trim_head_frames=trim_head_frames,
            trim_tail_frames=trim_tail_frames,
            with_audio=with_audio,
            width=output_width,
            height=output_height,
        )
        args = ["ffmpeg", "-y"]
        for p in paths:
            args += ["-i", str(p)]
        args += ["-filter_complex", filt, "-map", video_label]
        if map_audio:
            args += ["-map", map_audio, "-c:a", "aac", "-b:a", "192k"]
        args += ["-c:v", "libx264", "-preset", "fast", "-crf", str(crf), "-pix_fmt", "yuv420p", str(out_path)]
        logs.append(_run_ffmpeg(args))
        return {"path": str(out_path), "filename": out_path.name, "log": "\n".join(logs)}

    if no_fade:
        _hard_concat(paths, out_path)
        return {"path": str(out_path), "filename": out_path.name, "log": "hard concat"}

    video_filter = _build_xfade_filter(len(paths), segment_sec=segment_sec, fade=fade)
    audio_filter = _build_audio_acrossfade(len(paths), fade=fade) if with_audio else None
    filter_complex = video_filter
    if audio_filter:
        filter_complex += f";{audio_filter}"
    args = ["ffmpeg", "-y"]
    for p in paths:
        args += ["-i", str(p)]
    args += ["-filter_complex", filter_complex, "-map", "[vout]"]
    if audio_filter:
        args += ["-map", "[aout]", "-c:a", "aac", "-b:a", "192k"]
    args += ["-c:v", "libx264", "-preset", "fast", "-crf", str(crf), "-pix_fmt", "yuv420p", str(out_path)]
    logs.append(_run_ffmpeg(args))
    return {"path": str(out_path), "filename": out_path.name, "log": "\n".join(logs)}
