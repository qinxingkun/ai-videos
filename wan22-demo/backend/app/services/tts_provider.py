from __future__ import annotations

import asyncio
import shlex
from pathlib import Path
from typing import Protocol

from app.config import Settings
from app.services.http_client import async_client
from app.services.dubbing_timeline import PCM_SAMPLE_RATE, TimelineItem


class ProviderUnavailable(RuntimeError):
    pass


class TTSProvider(Protocol):
    name: str
    degraded: bool

    async def synthesize(
        self, item: TimelineItem, output: Path, *, speed: float = 1.0
    ) -> None: ...


async def _run_cli(command: str, values: dict[str, str]) -> None:
    args = [part.format_map(values) for part in shlex.split(command)]
    process = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    if process.returncode:
        raise RuntimeError((stderr or stdout or b"provider command failed").decode(errors="replace")[-800:])


class CosyVoiceHTTPProvider:
    name = "cosyvoice-http"
    degraded = False

    def __init__(self, url: str, timeout: float):
        self.url = url
        self.timeout = timeout

    async def synthesize(
        self, item: TimelineItem, output: Path, *, speed: float = 1.0
    ) -> None:
        async with async_client(timeout=self.timeout) as client:
            response = await client.post(
                self.url,
                json={
                    "text": item.text,
                    "speaker": item.speaker,
                    "voice_id": item.voice_id,
                    "sample_rate": PCM_SAMPLE_RATE,
                    "speed": speed,
                },
            )
            response.raise_for_status()
            output.write_bytes(response.content)


class CosyVoiceCLIProvider:
    name = "cosyvoice-cli"
    degraded = False

    def __init__(self, command: str):
        self.command = command

    async def synthesize(
        self, item: TimelineItem, output: Path, *, speed: float = 1.0
    ) -> None:
        await _run_cli(
            self.command,
            {
                "text": item.text,
                "speaker": item.speaker or "",
                "voice_id": item.voice_id or "",
                "speed": f"{speed:.4f}",
                "output": str(output),
            },
        )


class SilenceFallbackProvider:
    name = "silence-fallback"
    degraded = True

    async def synthesize(
        self, item: TimelineItem, output: Path, *, speed: float = 1.0
    ) -> None:
        duration = item.duration_samples / PCM_SAMPLE_RATE
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            f"anullsrc=r={PCM_SAMPLE_RATE}:cl=stereo:d={duration:.9f}",
            "-c:a", "pcm_s16le", str(output),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode:
            raise RuntimeError(stderr.decode(errors="replace")[-800:])


def create_tts_provider(settings: Settings) -> TTSProvider:
    if settings.cosyvoice_url:
        return CosyVoiceHTTPProvider(settings.cosyvoice_url, settings.provider_timeout_sec)
    if settings.cosyvoice_cli:
        return CosyVoiceCLIProvider(settings.cosyvoice_cli)
    if settings.tts_provider_mode == "preferred":
        return SilenceFallbackProvider()
    raise ProviderUnavailable("CosyVoice provider is required but neither HTTP nor CLI is configured")
