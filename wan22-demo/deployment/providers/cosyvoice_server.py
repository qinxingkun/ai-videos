from __future__ import annotations

import argparse
import asyncio
import io
import shutil
import sys
import tempfile
from pathlib import Path

import torch
import torchaudio
import uvicorn
import onnxruntime as ort
import soundfile as sf
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field


class SynthesisRequest(BaseModel):
    text: str = Field(min_length=1)
    speaker: str | None = None
    voice_id: str | None = None
    sample_rate: int = 48_000
    speed: float = Field(default=1.0, ge=0.95, le=1.05)


def _resolve_voice(voice_root: Path, voice_id: str | None, default_voice: str | None) -> Path:
    selected = voice_id or default_voice
    if not selected:
        raise HTTPException(422, "voice_id is required when no default voice is configured")
    candidate = (voice_root / selected).resolve()
    root = voice_root.resolve()
    if candidate != root and root not in candidate.parents:
        raise HTTPException(422, "voice_id must resolve inside voice_root")
    if not candidate.is_file():
        raise HTTPException(422, f"voice reference not found: {selected}")
    return candidate


def create_app(
    *,
    cosyvoice_root: Path,
    model_dir: Path,
    voice_root: Path,
    default_voice: str | None,
    whisper_checkpoint: Path | None = None,
) -> FastAPI:
    ort.preload_dlls()
    sys.path.insert(0, str(cosyvoice_root))
    sys.path.insert(0, str(cosyvoice_root / "third_party" / "Matcha-TTS"))
    from cosyvoice.cli.cosyvoice import AutoModel

    model = AutoModel(model_dir=str(model_dir))
    inference_lock = asyncio.Lock()
    whisper_model = None
    app = FastAPI(title="CosyVoice 3 production adapter")

    @app.get("/health")
    async def health() -> dict:
        return {
            "ok": True,
            "model": str(model_dir),
            "sampleRate": model.sample_rate,
            "busy": inference_lock.locked(),
        }

    def _run_synthesis(text: str, prompt_wav: Path, speed: float) -> list:
        return [
            result["tts_speech"].detach().cpu()
            for result in model.inference_cross_lingual(
                text,
                str(prompt_wav),
                stream=False,
                speed=speed,
            )
        ]

    @app.post("/synthesize")
    async def synthesize(body: SynthesisRequest) -> Response:
        prompt_wav = _resolve_voice(voice_root, body.voice_id, default_voice)
        text = body.text
        if "<|endofprompt|>" not in text:
            text = f"You are a helpful assistant.<|endofprompt|>{text}"
        async with inference_lock:
            chunks = await asyncio.to_thread(_run_synthesis, text, prompt_wav, body.speed)
        if not chunks:
            raise HTTPException(500, "CosyVoice returned no audio")
        waveform = torch.cat(chunks, dim=1)
        if model.sample_rate != body.sample_rate:
            waveform = torchaudio.functional.resample(waveform, model.sample_rate, body.sample_rate)
        buffer = io.BytesIO()
        sf.write(
            buffer,
            waveform.squeeze(0).numpy(),
            body.sample_rate,
            format="WAV",
            subtype="PCM_16",
        )
        return Response(buffer.getvalue(), media_type="audio/wav")

    @app.post("/transcribe")
    async def transcribe(audio: UploadFile = File(...)) -> dict:
        nonlocal whisper_model
        if whisper_checkpoint is None or not whisper_checkpoint.is_file():
            raise HTTPException(503, "Whisper QA checkpoint is not configured")
        work = Path(tempfile.mkdtemp(prefix="cosyvoice-asr-"))
        try:
            audio_path = work / "audio.wav"
            audio_path.write_bytes(await audio.read())
            async with inference_lock:
                if whisper_model is None:
                    import whisper

                    whisper_model = whisper.load_model(str(whisper_checkpoint))
                result = await asyncio.to_thread(
                    whisper_model.transcribe,
                    str(audio_path),
                    fp16=torch.cuda.is_available(),
                )
            return {"text": str(result.get("text") or "").strip()}
        finally:
            shutil.rmtree(work, ignore_errors=True)

    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cosyvoice-root", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--voice-root", type=Path, required=True)
    parser.add_argument("--default-voice")
    parser.add_argument("--whisper-checkpoint", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8191)
    args = parser.parse_args()
    app = create_app(
        cosyvoice_root=args.cosyvoice_root,
        model_dir=args.model_dir,
        voice_root=args.voice_root,
        default_voice=args.default_voice,
        whisper_checkpoint=args.whisper_checkpoint,
    )
    uvicorn.run(app, host=args.host, port=args.port, workers=1)


if __name__ == "__main__":
    main()
