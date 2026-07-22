from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.api import ImageGenerateRequest, LookbookRequest
from app.services import image as image_service
from app.services import instantid_lookbook


router = APIRouter(prefix="/v1/images", tags=["images"])


def _body_dict(body: ImageGenerateRequest) -> dict:
    return body.model_dump(exclude_none=True)


@router.post("/t2i")
async def post_t2i(body: ImageGenerateRequest) -> dict:
    try:
        return await image_service.generate_image_t2i(_body_dict(body))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/lookbook")
async def post_lookbook(body: LookbookRequest) -> dict:
    """InstantID：参考脸 → 定妆照 / 段首帧（阶段 0）。"""
    try:
        return instantid_lookbook.generate_lookbook(**body.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/lookbook/status")
async def lookbook_status() -> dict:
    return {
        "configured": instantid_lookbook.is_configured(),
        "missing": instantid_lookbook.missing_components(),
    }


@router.get("/tasks/{task_id}")
async def get_task(task_id: str) -> dict:
    try:
        return await image_service.get_image_task({"task_id": task_id})
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
