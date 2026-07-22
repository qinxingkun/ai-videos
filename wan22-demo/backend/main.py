"""FastAPI 入口：python main.py"""

from __future__ import annotations

import os

import uvicorn

from app.config import get_settings


def main() -> None:
    settings = get_settings()
    host = os.getenv("HOST", settings.host)
    port = int(os.getenv("PORT", str(settings.port)))
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=os.getenv("RELOAD", "").lower() in ("1", "true", "yes"),
    )


if __name__ == "__main__":
    main()
