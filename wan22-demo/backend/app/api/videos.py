from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.api import VideoGenerateRequest
from app.services import video as video_service

router = APIRouter(prefix="/v1/videos", tags=["videos"])


def _args(body: VideoGenerateRequest) -> dict:
    return body.model_dump(exclude_none=True)


@router.post("/t2v")
async def post_t2v(body: VideoGenerateRequest) -> dict:
    try:
        return await video_service.generate_video_t2v(_args(body))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/i2v")
async def post_i2v(body: VideoGenerateRequest) -> dict:
    try:
        return await video_service.generate_video_i2v(_args(body))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/flf2v")
async def post_flf2v(body: VideoGenerateRequest) -> dict:
    try:
        return await video_service.generate_video_flf2v(_args(body))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/tasks/{task_id}")
async def get_task(task_id: str) -> dict:
    try:
        return await video_service.get_video_task({"task_id": task_id})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
