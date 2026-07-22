from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.config import get_settings
from app.services.media_probe import probe_media


def _health_url(endpoint: str) -> str:
    split = urlsplit(endpoint)
    return urlunsplit((split.scheme, split.netloc, "/health", "", ""))


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test production dubbing providers")
    parser.add_argument("--video", type=Path, help="25fps close-up video for real LatentSync")
    parser.add_argument("--audio", type=Path, help="16k/48k WAV matching --video")
    args = parser.parse_args()
    settings = get_settings()
    endpoints = {
        "CosyVoice": settings.cosyvoice_url,
        "LatentSync": settings.latentsync_url,
        "ASR": settings.asr_qa_url,
        "SyncNet": settings.syncnet_qa_url,
    }
    with httpx.Client(timeout=settings.provider_timeout_sec) as client:
        for name, endpoint in endpoints.items():
            if not endpoint:
                raise SystemExit(f"{name} endpoint is not configured")
            response = client.get(_health_url(endpoint))
            response.raise_for_status()
            print(f"{name}: health ok")

        tts = client.post(
            settings.cosyvoice_url,
            json={
                "text": "你好，这是多人配音服务检查。",
                "speaker": "smoke",
                "voice_id": "default.wav",
                "sample_rate": 48_000,
                "speed": 1.0,
            },
        )
        tts.raise_for_status()
        with tempfile.TemporaryDirectory(prefix="dub-provider-smoke-") as work:
            wav = Path(work) / "tts.wav"
            wav.write_bytes(tts.content)
            if probe_media(wav)["audioStreams"][0]["sample_rate"] != 48_000:
                raise SystemExit("CosyVoice smoke output is not 48kHz")
            print("CosyVoice: synthesize ok")

            if args.video or args.audio:
                if not args.video or not args.audio:
                    raise SystemExit("--video and --audio must be supplied together")
                with args.video.open("rb") as video, args.audio.open("rb") as audio:
                    synced = client.post(
                        settings.latentsync_url,
                        files={
                            "video": (args.video.name, video, "video/mp4"),
                            "audio": (args.audio.name, audio, "audio/wav"),
                        },
                        data={"request_id": "provider-smoke", "seed": "1247"},
                    )
                synced.raise_for_status()
                output = Path(work) / "synced.mp4"
                output.write_bytes(synced.content)
                if not probe_media(output)["videoStreams"]:
                    raise SystemExit("LatentSync smoke produced no video stream")
                print("LatentSync: inference ok")


if __name__ == "__main__":
    main()
