from __future__ import annotations

import argparse
import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import torch
from diffusers import DiffusionPipeline

DEFAULT_NEGATIVE = (
    "低分辨率，低画质，肢体畸形，手指畸形，画面过饱和，蜡像感，人脸无细节，"
    "过度光滑，画面具有AI感。构图混乱。文字模糊，扭曲。"
)


class ServerState:
    def __init__(self, *, model_dir: Path, device: str | None = None) -> None:
        resolved_device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        dtype = torch.bfloat16 if resolved_device == "cuda" else torch.float32
        self.model_dir = model_dir
        self.device = resolved_device
        self.dtype = dtype
        self.lock = threading.Lock()
        self.pipe = DiffusionPipeline.from_pretrained(str(model_dir), torch_dtype=dtype)
        self.pipe = self.pipe.to(resolved_device)

    def health(self) -> dict[str, Any]:
        return {
            "ok": True,
            "model": str(self.model_dir),
            "device": self.device,
            "dtype": str(self.dtype),
            "busy": self.lock.locked(),
        }

    def generate(self, body: dict[str, Any]) -> bytes:
        prompt = str(body.get("prompt") or "").strip()
        if not prompt:
            raise ValueError("prompt required")
        negative_prompt = str(body.get("negative_prompt") or DEFAULT_NEGATIVE)
        width = int(body.get("width") or 1328)
        height = int(body.get("height") or 1328)
        turbo = bool(body.get("turbo"))
        steps = 4 if turbo else int(body.get("steps") or 50)
        cfg = 1.0 if turbo else float(body.get("cfg") if body.get("cfg") is not None else 4.0)
        seed = body.get("seed")
        generator = None
        if seed is not None:
            gen_device = self.device if self.device == "cuda" else "cpu"
            generator = torch.Generator(device=gen_device).manual_seed(int(seed))

        with self.lock:
            result = self.pipe(
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                num_inference_steps=steps,
                true_cfg_scale=cfg,
                generator=generator,
            )
            image = result.images[0]
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()


def make_handler(state: ServerState):
    class Handler(BaseHTTPRequestHandler):
        server_version = "QwenImageServer/1.0"

        def log_message(self, fmt: str, *args) -> None:
            print(f"[qwen-image] {self.address_string()} - {fmt % args}")

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length > 0 else b"{}"
            parsed = json.loads(raw.decode("utf-8") or "{}")
            if not isinstance(parsed, dict):
                raise ValueError("JSON body must be an object")
            return parsed

        def do_GET(self) -> None:
            if self.path.rstrip("/") == "/health":
                self._send_json(200, state.health())
                return
            self._send_json(404, {"detail": "not found"})

        def do_POST(self) -> None:
            if self.path.rstrip("/") != "/generate":
                self._send_json(404, {"detail": "not found"})
                return
            try:
                body = self._read_json()
                png = state.generate(body)
            except ValueError as exc:
                self._send_json(422, {"detail": str(exc)})
                return
            except Exception as exc:
                self._send_json(500, {"detail": str(exc)})
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(png)))
            self.end_headers()
            self.wfile.write(png)

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Qwen-Image-2512 diffusers inference server")
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path("/mnt/ddr1/ai-models/models-download/qwen/Qwen-Image-2512"),
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8192)
    parser.add_argument("--device", default=None)
    args = parser.parse_args()
    if not args.model_dir.is_dir():
        raise SystemExit(f"model dir not found: {args.model_dir}")

    print(f"[qwen-image] loading model from {args.model_dir} ...")
    state = ServerState(model_dir=args.model_dir, device=args.device)
    handler = make_handler(state)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"[qwen-image] listening on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
