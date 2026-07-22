from __future__ import annotations

import asyncio
import json
import math
import re
from pathlib import Path

from app.services.dubbing_timeline import DubbingTimeline, PCM_SAMPLE_RATE


async def _run(args: list[str]) -> tuple[str, str]:
    process = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    out = stdout.decode(errors="replace")
    err = stderr.decode(errors="replace")
    if process.returncode:
        raise RuntimeError((err or out)[-1200:])
    return out, err


async def mix_pcm(
    clips: list[Path], timeline: DubbingTimeline, output: Path
) -> None:
    if len(clips) != len(timeline.items):
        raise ValueError("audio clips must match timeline items")
    if not clips:
        duration = timeline.duration_samples / PCM_SAMPLE_RATE
        await _run(
            [
                "ffmpeg", "-y", "-f", "lavfi", "-i",
                f"anullsrc=r={PCM_SAMPLE_RATE}:cl=stereo:d={duration:.9f}",
                "-c:a", "pcm_s16le", str(output),
            ]
        )
        return
    args = ["ffmpeg", "-y"]
    for clip in clips:
        args += ["-i", str(clip)]
    labels: list[str] = []
    filters: list[str] = []
    for index, item in enumerate(timeline.items):
        label = f"a{index}"
        filters.append(
            f"[{index}:a]aresample={PCM_SAMPLE_RATE},adelay={item.start_sample}S:all=1[{label}]"
        )
        labels.append(f"[{label}]")
    filters.append(
        f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0,"
        f"apad,atrim=end_sample={timeline.duration_samples},asetpts=PTS-STARTPTS[out]"
    )
    await _run(
        args + ["-filter_complex", ";".join(filters), "-map", "[out]",
                "-ar", str(PCM_SAMPLE_RATE), "-ac", "2", "-c:a", "pcm_s16le", str(output)]
    )


def _loudnorm_json(stderr: str) -> dict:
    matches = re.findall(r"\{\s*\"input_i\".*?\}", stderr, flags=re.S)
    if not matches:
        raise RuntimeError("ffmpeg loudnorm analysis did not return measurements")
    return json.loads(matches[-1])


async def loudnorm_two_pass(source: Path, output: Path) -> dict:
    _, analysis = await _run(
        ["ffmpeg", "-i", str(source), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
         "-f", "null", "-"]
    )
    measured = _loudnorm_json(analysis)
    values = ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")
    finite = all(math.isfinite(float(measured[key])) for key in values)
    if finite:
        af = (
            "loudnorm=I=-16:TP=-1.5:LRA=11:linear=true:"
            f"measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:"
            f"measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}:"
            f"offset={measured['target_offset']}"
        )
    else:
        # Digital silence has -inf measurements. Keep the required second pass
        # but let loudnorm use dynamic mode rather than passing invalid -inf.
        af = "loudnorm=I=-16:TP=-1.5:LRA=11:linear=false"
    await _run(
        ["ffmpeg", "-y", "-i", str(source), "-af", af, "-ar", str(PCM_SAMPLE_RATE),
         "-ac", "2", "-c:a", "pcm_s16le", str(output)]
    )
    # Sparse dialogue followed by long silence can make FFmpeg's linear second
    # pass miss the target because of EBU gating. Measure the PCM result and
    # apply a deterministic gain correction before the single final AAC encode.
    _, verification = await _run(
        [
            "ffmpeg", "-i", str(output),
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
            "-f", "null", "-",
        ]
    )
    verified = _loudnorm_json(verification)
    output_i = float(verified["input_i"])
    output_tp = float(verified["input_tp"])
    if math.isfinite(output_i) and abs(output_i - (-16.0)) > 0.35:
        gain = -16.0 - output_i
        if math.isfinite(output_tp):
            gain = min(gain, -1.5 - output_tp)
        corrected = output.with_name(f".{output.stem}.corrected.wav")
        await _run(
            [
                "ffmpeg", "-y", "-i", str(output),
                "-af", f"volume={gain:.4f}dB",
                "-ar", str(PCM_SAMPLE_RATE), "-ac", "2",
                "-c:a", "pcm_s16le", str(corrected),
            ]
        )
        corrected.replace(output)
        measured["postGainCorrectionDb"] = round(gain, 4)
    measured["verifiedInputI"] = verified.get("input_i")
    measured["verifiedInputTp"] = verified.get("input_tp")
    return measured


async def mux_final(video: Path, normalized_pcm: Path, output: Path) -> None:
    # AAC is encoded exactly once, at the final container boundary. Deliberately
    # no -shortest: timeline errors must remain observable to AV QA.
    await _run(
        ["ffmpeg", "-y", "-i", str(video), "-i", str(normalized_pcm),
         "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output)]
    )
