from __future__ import annotations

import asyncio
import json
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import ROOT, settings
from .gpu import query_gpus
from .jobs import JobBuildError, build_payload, upstream_for_mode
from .models import JobCreate, JobRecord, Mode

app = FastAPI(title="H3 Studio", version="0.1.0")
WEB_DIR = ROOT / "web"

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Local job metadata keyed by upstream video id.
JOBS: dict[str, JobRecord] = {}
HISTORY: list[str] = []


def _upstream_base(kind: str) -> str:
    if kind == "fl2va":
        return settings.fl2va_url.rstrip("/")
    if kind == "ref2va":
        return settings.ref2va_url.rstrip("/")
    raise HTTPException(400, f"unknown upstream kind: {kind}")


async def _probe(url: str) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{url.rstrip('/')}/health", headers=settings.auth_headers())
            ok = r.status_code == 200
            body: Any
            try:
                body = r.json()
            except Exception:
                body = r.text[:200]
            return {"ok": ok, "status_code": r.status_code, "body": body, "url": url}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "url": url}


@app.get("/api/health")
async def health() -> dict[str, Any]:
    fl2va, ref2va = await asyncio.gather(
        _probe(settings.fl2va_url),
        _probe(settings.ref2va_url),
    )
    return {
        "ok": True,
        "fl2va": fl2va,
        "ref2va": ref2va,
        "fl2va_url": settings.fl2va_url,
        "ref2va_url": settings.ref2va_url,
    }


@app.get("/api/gpu")
async def gpu_once() -> dict[str, Any]:
    return {"gpus": await query_gpus(), "ts": time.time()}


@app.websocket("/api/ws/gpu")
async def gpu_ws(ws: WebSocket) -> None:
    await ws.accept()
    try:
        while True:
            payload = {"gpus": await query_gpus(), "ts": time.time()}
            await ws.send_text(json.dumps(payload))
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        return
    except Exception:
        try:
            await ws.close()
        except Exception:
            pass


@app.post("/api/uploads")
async def upload(file: UploadFile = File(...)) -> dict[str, Any]:
    if not file.filename:
        raise HTTPException(400, "missing filename")

    suffix = Path(file.filename).suffix.lower()
    allowed = {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".bmp",
        ".mp4",
        ".mov",
        ".webm",
        ".mkv",
        ".mp3",
        ".wav",
        ".m4a",
        ".aac",
        ".flac",
        ".ogg",
    }
    if suffix not in allowed:
        raise HTTPException(400, f"unsupported file type: {suffix}")

    media_type = "image"
    if suffix in {".mp4", ".mov", ".webm", ".mkv"}:
        media_type = "video"
    elif suffix in {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}:
        media_type = "audio"

    dest_name = f"{uuid.uuid4().hex}{suffix}"
    dest = settings.upload_dir / dest_name
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    abs_path = dest.resolve()
    return {
        "id": dest_name,
        "filename": file.filename,
        "type": media_type,
        "path": str(abs_path),
        "uri": abs_path.as_uri(),
        "url": f"/api/files/uploads/{dest_name}",
    }


@app.post("/api/jobs")
async def create_job(body: JobCreate) -> dict[str, Any]:
    try:
        kind = upstream_for_mode(body.mode)
        payload = build_payload(body)
    except JobBuildError as exc:
        raise HTTPException(400, str(exc)) from exc

    base = _upstream_base(kind)
    probe = await _probe(base)
    if not probe.get("ok"):
        raise HTTPException(
            503,
            detail={
                "message": f"{kind.upper()} upstream not ready",
                "upstream": base,
                "probe": probe,
            },
        )

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(f"{base}/v1/videos", json=payload, headers=settings.auth_headers())
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"upstream request failed: {exc}") from exc

    if r.status_code >= 400:
        raise HTTPException(
            r.status_code,
            detail={"message": "upstream rejected job", "body": _safe_body(r)},
        )

    data = r.json()
    job_id = data.get("id")
    if not job_id:
        raise HTTPException(502, f"upstream returned no id: {data}")

    record = JobRecord(
        id=job_id,
        mode=body.mode,
        upstream=kind,
        task=payload["task"],
        status=data.get("status", "queued"),
        progress=data.get("progress", 0),
        created_at=data.get("created_at"),
        size=data.get("size"),
        seconds=data.get("seconds"),
        prompt=body.prompt[:500],
    )
    JOBS[job_id] = record
    HISTORY.insert(0, job_id)
    del HISTORY[100:]

    return {"job": record.model_dump(), "upstream_response": data, "payload": payload}


@app.get("/api/jobs")
async def list_jobs() -> dict[str, Any]:
    items = []
    for jid in HISTORY:
        rec = JOBS.get(jid)
        if rec:
            items.append(rec.model_dump())
    return {"jobs": items}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    rec = JOBS.get(job_id)
    kind = rec.upstream if rec else None

    # Fall back to probing both upstreams if unknown.
    bases: list[str] = []
    if kind:
        bases.append(_upstream_base(kind))
    else:
        bases.extend([settings.fl2va_url.rstrip("/"), settings.ref2va_url.rstrip("/")])

    last_err: str | None = None
    data: dict[str, Any] | None = None
    used_base = ""
    async with httpx.AsyncClient(timeout=30.0) as client:
        for base in bases:
            try:
                r = await client.get(f"{base}/v1/videos/{job_id}", headers=settings.auth_headers())
                if r.status_code == 404:
                    continue
                if r.status_code >= 400:
                    last_err = f"{base}: {_safe_body(r)}"
                    continue
                data = r.json()
                used_base = base
                break
            except httpx.HTTPError as exc:
                last_err = str(exc)

    if data is None:
        raise HTTPException(404, last_err or "job not found on upstream")

    if rec is None:
        # Infer upstream kind from URL
        inferred = "fl2va" if "30010" in used_base else "ref2va"
        rec = JobRecord(
            id=job_id,
            mode=Mode.t2va,
            upstream=inferred,
            task=str(data.get("task") or "unknown"),
        )
        JOBS[job_id] = rec
        HISTORY.insert(0, job_id)

    rec.status = data.get("status", rec.status)
    rec.progress = data.get("progress", rec.progress)
    rec.size = data.get("size", rec.size)
    rec.seconds = data.get("seconds", rec.seconds)
    rec.inference_time_s = data.get("inference_time_s", rec.inference_time_s)
    rec.peak_memory_mb = data.get("peak_memory_mb", rec.peak_memory_mb)
    rec.error = data.get("error", rec.error)
    rec.file_path = data.get("file_path", rec.file_path)
    JOBS[job_id] = rec

    return {"job": rec.model_dump(), "upstream_response": data}


@app.get("/api/jobs/{job_id}/content")
async def job_content(job_id: str) -> FileResponse:
    rec = JOBS.get(job_id)
    kind = rec.upstream if rec else "fl2va"
    base = _upstream_base(kind)

    local = settings.output_dir / f"{job_id}.mp4"
    if not local.exists() or local.stat().st_size == 0:
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                r = await client.get(
                    f"{base}/v1/videos/{job_id}/content",
                    headers=settings.auth_headers(),
                )
        except httpx.HTTPError as exc:
            # try the other upstream
            other = settings.ref2va_url if kind == "fl2va" else settings.fl2va_url
            try:
                async with httpx.AsyncClient(timeout=300.0) as client:
                    r = await client.get(
                        f"{other.rstrip('/')}/v1/videos/{job_id}/content",
                        headers=settings.auth_headers(),
                    )
            except httpx.HTTPError as exc2:
                raise HTTPException(502, f"download failed: {exc}; {exc2}") from exc2

        if r.status_code >= 400:
            raise HTTPException(r.status_code, _safe_body(r))
        local.write_bytes(r.content)

    return FileResponse(local, media_type="video/mp4", filename=f"{job_id}.mp4")


def _safe_body(r: httpx.Response) -> Any:
    try:
        return r.json()
    except Exception:
        return r.text[:1000]


app.mount(
    "/api/files/uploads",
    StaticFiles(directory=str(settings.upload_dir)),
    name="uploads",
)
app.mount(
    "/api/files/outputs",
    StaticFiles(directory=str(settings.output_dir)),
    name="outputs",
)


# Catch-all UI mount must stay after /api routes so they keep priority.
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
