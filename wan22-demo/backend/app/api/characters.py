from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.api import CharacterUpsertRequest
from app.services import characters

router = APIRouter(prefix="/v1/characters", tags=["characters"])


@router.get("")
async def list_characters() -> dict:
    return {"characters": characters.load_characters()}


@router.post("")
async def upsert_character(body: CharacterUpsertRequest) -> dict:
    return characters.upsert_character(body.id, body.name, body.character)


@router.delete("/{character_id}")
async def delete_character(character_id: str) -> dict:
    return characters.delete_character(character_id)
