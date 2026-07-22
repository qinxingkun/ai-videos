from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import characters, health, images, media, videos
from app.config import get_settings

settings = get_settings()

app = FastAPI(title="wan22-demo API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(videos.router)
app.include_router(images.router)
app.include_router(media.router)
app.include_router(characters.router)


@app.get("/")
async def root():
    return {
        "service": "wan22-demo-fastapi",
        "docs": "/docs",
        "health": "/health",
        "videos": "/v1/videos",
        "images": "/v1/images",
        "media": "/v1/media",
        "characters": "/v1/characters",
    }
