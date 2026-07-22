from __future__ import annotations

import asyncio
import wave
from pathlib import Path

from app.services.dubbing_timeline import PCM_SAMPLE_RATE
from app.services.media_probe import probe_media


def _atempo_chain(speed: float) -> str:
    factors: list[float] = []
    while speed > 2.0:
        factors.append(2.0)
        speed /= 2.0
    while speed < 0.5:
        factors.append(0.5)
        speed /= 0.5
    factors.append(speed)
    return ",".join(f"atempo={factor:.9f}" for factor in factors)


async def fit_audio(
    source: str | Path,
    output: str | Path,
    *,
    target_samples: int,
    sample_rate: int = PCM_SAMPLE_RATE,
    max_speedup: float = 1.05,
) -> dict:
    source = Path(source)
    output = Path(output)
    duration = probe_media(source)["duration"]
    target = target_samples / sample_rate
    if duration <= 0 or target <= 0:
        raise ValueError("source and target durations must be positive")
    speed = duration / target
    if speed > max_speedup + 1e-6:
        raise RuntimeError(
            f"speech exceeds slot by {(speed - 1):.2%}; "
            "maximum cumulative speedup is 5%; "
            f"remaining limit is {(max_speedup - 1):.2%}"
        )
    filters = []
    mode = "pad"
    if speed > 1.0:
        filters.append(_atempo_chain(speed))
        mode = "speedup"
    filters += [
        f"aresample={sample_rate}",
        "apad",
        f"atrim=duration={target:.9f}",
        "asetpts=PTS-STARTPTS",
    ]
    af = ",".join(filters)
    process = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", str(source), "-vn", "-af", af,
        "-ar", str(sample_rate), "-ac", "2", "-c:a", "pcm_s16le", str(output),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode:
        raise RuntimeError(stderr.decode(errors="replace")[-800:])
    if output.is_file():
        with wave.open(str(output), "rb") as wav:
            if wav.getframerate() != sample_rate:
                raise RuntimeError(f"fitted PCM sample rate {wav.getframerate()} != {sample_rate}")
            actual_samples = wav.getnframes()
        if actual_samples != target_samples:
            raise RuntimeError(
                f"fitted PCM samples {actual_samples} != target {target_samples}"
            )
        actual = actual_samples / sample_rate
        drift = 0.0
    else:  # Allows command-construction unit tests to mock ffmpeg without writing a file.
        actual = probe_media(output)["duration"]
        actual_samples = round(actual * sample_rate)
        drift = abs(actual - target) / target
    return {
        "path": str(output),
        "targetDuration": target,
        "duration": actual,
        "samples": actual_samples,
        "drift": drift,
        "mode": mode,
        "speed": speed if mode == "speedup" else 1.0,
    }
