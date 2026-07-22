from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response

from app.config import get_settings
from app.services.http_client import async_client
from app.schemas.api import (
    AnalyzeSpliceRequest,
    AnimateRelockRequest,
    ConcatRequest,
    DetectDuplicatesRequest,
    DetectFaceRequest,
    DubAnalyzeRequest,
    DubRenderRequest,
    DubRequest,
    ExtractFrameRequest,
    NormalizeSegmentRequest,
    ValidateFinalRequest,
    ValidateSegmentRequest,
)
from app.services import media_ops
from app.services import dubbing_session
from app.services import video_catalog
from app.services.comfy_client import ComfyClient
from app.services.dubbing_session import DubbingSessionError

router = APIRouter(prefix="/v1/media", tags=["media"])


def _raise_dub_error(exc: Exception) -> None:
    if isinstance(exc, DubbingSessionError):
        raise HTTPException(status_code=exc.http_status, detail=exc.to_detail()) from exc
    raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/recent-videos")
async def recent_videos(limit: int = Query(50, ge=1, le=100)):
    settings = get_settings()
    return video_catalog.list_recent_videos(settings.video_dir, limit=limit)


def _local_media_path(settings, *, filename: str, subfolder: str, type_: str) -> Path:
    safe_name = Path(filename).name
    base = settings.comfyui_root / type_
    clean_subfolder = subfolder.strip("/\\")
    return base / clean_subfolder / safe_name if clean_subfolder else base / safe_name


@router.get("/view")
async def view_media(
    filename: str = Query(...),
    subfolder: str = Query(""),
    type: str = Query("output"),
):
    settings = get_settings()
    local_path = _local_media_path(settings, filename=filename, subfolder=subfolder, type_=type)
    if local_path.is_file():
        return FileResponse(local_path)

    params = {"filename": filename, "subfolder": subfolder, "type": type}
    try:
        async with async_client(base_url=settings.comfyui_url, timeout=120.0) as client:
            r = await client.get("/view", params=params)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"文件不存在且 ComfyUI 不可达（{settings.comfyui_url}）: {exc}",
        ) from exc
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text[:300])
    content_type = r.headers.get("content-type", "application/octet-stream")
    return Response(content=r.content, media_type=content_type)


@router.post("/upload")
async def upload_media(file: UploadFile = File(...), subfolder: str = "", overwrite: bool = True):
    content = await file.read()
    comfy = ComfyClient()
    try:
        return comfy._upload_image_local(
            content, file.filename or "upload.png", subfolder=subfolder, overwrite=overwrite
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


def _run(fn, body):
    try:
        return fn(body.model_dump(exclude_none=True))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/extract-frame")
async def extract_frame(body: ExtractFrameRequest) -> dict:
    return _run(media_ops.extract_video_frame, body)


@router.post("/concat")
async def concat(body: ConcatRequest) -> dict:
    return _run(media_ops.concat_segments, body)


@router.post("/analyze-splice")
async def analyze_splice(body: AnalyzeSpliceRequest) -> dict:
    return _run(media_ops.analyze_splice, body)


@router.post("/validate/segment")
async def validate_segment(body: ValidateSegmentRequest) -> dict:
    return _run(media_ops.validate_segment, body)


@router.post("/normalize-segment")
async def normalize_segment(body: NormalizeSegmentRequest) -> dict:
    return _run(media_ops.normalize_segment, body)


@router.post("/validate/final")
async def validate_final(body: ValidateFinalRequest) -> dict:
    return _run(media_ops.validate_final, body)


@router.post("/detect-duplicate-frames")
async def detect_duplicate_frames(body: DetectDuplicatesRequest) -> dict:
    return _run(media_ops.detect_duplicate_frames, body)


@router.post("/detect-face")
async def detect_face(body: DetectFaceRequest) -> dict:
    """无脸门控：条件图无人脸时前端应回退定妆照作为下一段起点。"""
    return _run(media_ops.detect_face_gate, body)


@router.post("/animate-relock")
async def animate_relock(body: AnimateRelockRequest) -> dict:
    return _run(media_ops.animate_relock, body)


@router.post("/dub")
async def dub(body: DubRequest) -> dict:
    try:
        return await media_ops.dub_media(body.model_dump(exclude_none=True))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/dub/analyze")
async def analyze_dub(body: DubAnalyzeRequest) -> dict:
    try:
        return await dubbing_session.analyze_dub_session(body.model_dump(exclude_none=True))
    except Exception as e:
        _raise_dub_error(e)


@router.post("/dub/render")
async def render_dub(body: DubRenderRequest) -> dict:
    try:
        return await dubbing_session.render_dub_session(body.model_dump(exclude_none=True))
    except Exception as e:
        _raise_dub_error(e)


@router.get("/dub/sessions/{session_id}")
async def get_dub_session(session_id: str) -> dict:
    try:
        return dubbing_session.load_dub_session(session_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/dub/sessions/{session_id}/tracks/{filename}")
async def get_dub_track_thumbnail(session_id: str, filename: str):
    try:
        return FileResponse(dubbing_session.track_thumbnail_path(session_id, filename))
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
