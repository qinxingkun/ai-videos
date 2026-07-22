from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import torch
import uvicorn
import onnxruntime as ort
from accelerate.utils import set_seed
from DeepCache import DeepCacheSDHelper
from diffusers import AutoencoderKL, DDIMScheduler
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from omegaconf import OmegaConf

ort.preload_dlls()


def _video_shape(path: Path) -> tuple[int, float]:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-count_frames",
            "-select_streams", "v:0",
            "-show_entries", "stream=nb_read_frames,avg_frame_rate",
            "-of", "json", str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    stream = json.loads(result.stdout)["streams"][0]
    numerator, denominator = stream["avg_frame_rate"].split("/", 1)
    return int(stream["nb_read_frames"]), float(numerator) / float(denominator)


def _lock_output_frames(source: Path, output: Path) -> None:
    expected_frames, fps = _video_shape(source)
    actual_frames, _ = _video_shape(output)
    if actual_frames == expected_frames:
        return
    normalized = output.with_name("output_normalized.mp4")
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-i", str(output), "-an",
            "-vf", f"fps={fps},setpts=PTS-STARTPTS",
            "-frames:v", str(expected_frames), "-r", str(fps), "-fps_mode", "cfr",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(normalized),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError(result.stderr[-800:])
    normalized.replace(output)
    final_frames, _ = _video_shape(output)
    if final_frames != expected_frames:
        raise RuntimeError(
            f"LatentSync normalized frames {final_frames} != input {expected_frames}"
        )


class LatentSyncEngine:
    def __init__(self, root: Path, config_path: Path, checkpoint: Path):
        self.root = root
        sys.path.insert(0, str(root))
        from latentsync.models.unet import UNet3DConditionModel
        from latentsync.pipelines.lipsync_pipeline import LipsyncPipeline
        from latentsync.whisper.audio2feature import Audio2Feature

        self.config = OmegaConf.load(config_path)
        self.checkpoint = checkpoint
        self.lock = asyncio.Lock()
        self.syncnet = None

        if not torch.cuda.is_available():
            raise RuntimeError("LatentSync 1.6 requires CUDA")
        dtype = torch.float16 if torch.cuda.get_device_capability()[0] > 7 else torch.float32
        cross_attention_dim = self.config.model.cross_attention_dim
        whisper_name = "small.pt" if cross_attention_dim == 768 else "tiny.pt"
        audio_encoder = Audio2Feature(
            model_path=str(root / "checkpoints" / "whisper" / whisper_name),
            device="cuda",
            num_frames=self.config.data.num_frames,
            audio_feat_length=self.config.data.audio_feat_length,
        )
        vae = AutoencoderKL.from_pretrained(
            str(root / "checkpoints" / "sd-vae-ft-mse"),
            torch_dtype=dtype,
            local_files_only=True,
        )
        vae.config.scaling_factor = 0.18215
        vae.config.shift_factor = 0
        unet, _ = UNet3DConditionModel.from_pretrained(
            OmegaConf.to_container(self.config.model),
            str(checkpoint),
            device="cpu",
        )
        unet = unet.to(dtype=dtype)
        scheduler = DDIMScheduler.from_pretrained(str(root / "configs"))
        self.dtype = dtype
        self.pipeline = LipsyncPipeline(
            vae=vae,
            audio_encoder=audio_encoder,
            unet=unet,
            scheduler=scheduler,
        ).to("cuda")
        helper = DeepCacheSDHelper(pipe=self.pipeline)
        helper.set_params(cache_interval=3, cache_branch_id=0)
        helper.enable()

    def run(self, video: Path, audio: Path, output: Path, *, seed: int = 1247) -> None:
        set_seed(seed)
        self.pipeline(
            video_path=str(video),
            audio_path=str(audio),
            video_out_path=str(output),
            num_frames=self.config.data.num_frames,
            num_inference_steps=20,
            guidance_scale=1.5,
            weight_dtype=self.dtype,
            width=self.config.data.resolution,
            height=self.config.data.resolution,
            mask_image_path=self.config.data.mask_image_path,
            temp_dir=str(output.parent / "work"),
        )
        _lock_output_frames(video, output)

    def score_sync(self, video: Path, work: Path) -> tuple[int, float]:
        from eval.eval_sync_conf import syncnet_eval
        from eval.syncnet import SyncNetEval
        from eval.syncnet_detect import SyncNetDetector

        if self.syncnet is None:
            self.syncnet = SyncNetEval(device="cuda")
            self.syncnet.loadParameters(
                str(self.root / "checkpoints" / "auxiliary" / "syncnet_v2.model")
            )
        detect_dir = work / "detect_results"
        detector = SyncNetDetector(device="cuda", detect_results_dir=str(detect_dir))
        offset, confidence = syncnet_eval(
            self.syncnet,
            detector,
            str(video),
            str(work / "sync_temp"),
            detect_results_dir=str(detect_dir),
        )
        return int(offset), float(confidence)


def create_app(engine: LatentSyncEngine) -> FastAPI:
    app = FastAPI(title="LatentSync 1.6 production adapter")

    @app.get("/health")
    async def health() -> dict:
        return {"ok": True, "device": torch.cuda.get_device_name(0)}

    @app.post("/lipsync")
    async def lipsync(
        video: UploadFile = File(...),
        audio: UploadFile = File(...),
        face_track: str | None = Form(default=None),
        request_id: str | None = Form(default=None),
        seed: int = Form(default=1247),
    ) -> Response:
        work = Path(tempfile.mkdtemp(prefix="latentsync-api-"))
        try:
            video_path = work / "input.mp4"
            audio_path = work / "input.wav"
            output_path = work / "output.mp4"
            video_path.write_bytes(await video.read())
            audio_path.write_bytes(await audio.read())
            track_payload = json.loads(face_track) if face_track else None
            async with engine.lock:
                await asyncio.to_thread(
                    engine.run,
                    video_path,
                    audio_path,
                    output_path,
                    seed=seed,
                )
            if not output_path.is_file() or output_path.stat().st_size == 0:
                raise HTTPException(
                    500,
                    {
                        "code": "NO_OUTPUT",
                        "requestId": request_id,
                        "faceTrackId": (track_payload or {}).get("trackId"),
                    },
                )
            return Response(
                output_path.read_bytes(),
                media_type="video/mp4",
                headers={
                    "X-Request-Id": request_id or "",
                    "X-Face-Track-Id": str((track_payload or {}).get("trackId") or ""),
                },
            )
        except HTTPException:
            raise
        except RuntimeError as exc:
            code = "FACE_NOT_FOUND" if "Face not detected" in str(exc) else "INFERENCE_FAILED"
            raise HTTPException(
                422 if code == "FACE_NOT_FOUND" else 500,
                {
                    "code": code,
                    "message": str(exc),
                    "requestId": request_id,
                    "faceTrackId": (track_payload or {}).get("trackId") if "track_payload" in locals() else None,
                },
            ) from exc
        finally:
            shutil.rmtree(work, ignore_errors=True)

    @app.post("/sync-qa")
    async def sync_qa(
        video: UploadFile = File(...),
        face_track: str | None = Form(default=None),
    ) -> dict:
        work = Path(tempfile.mkdtemp(prefix="syncnet-qa-"))
        try:
            video_path = work / "input.mp4"
            video_path.write_bytes(await video.read())
            async with engine.lock:
                offset, confidence = await asyncio.to_thread(
                    engine.score_sync, video_path, work
                )
            track_payload = json.loads(face_track) if face_track else {}
            return {
                "offsetFrames": offset,
                "confidence": confidence,
                "faceTrackId": track_payload.get("trackId"),
            }
        finally:
            shutil.rmtree(work, ignore_errors=True)

    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--latentsync-root", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8192)
    args = parser.parse_args()
    root = args.latentsync_root.resolve()
    engine = LatentSyncEngine(
        root,
        (args.config or root / "configs" / "unet" / "stage2_512.yaml").resolve(),
        (args.checkpoint or root / "checkpoints" / "latentsync_unet.pt").resolve(),
    )
    uvicorn.run(create_app(engine), host=args.host, port=args.port, workers=1)


if __name__ == "__main__":
    main()
