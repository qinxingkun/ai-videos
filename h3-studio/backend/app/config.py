import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"


def _load_api_token() -> str | None:
    token = os.environ.get("MINIMAX_H3_API_TOKEN") or os.environ.get("CUSTOM_VIDEO_API_TOKEN")
    if token and token.strip():
        return token.strip()
    raw_path = os.environ.get("MINIMAX_H3_API_TOKEN_FILE")
    path = Path(raw_path) if raw_path else ROOT.parent / ".secrets" / "minimax_h3_api_token"
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return text or None


class Settings:
    def __init__(self) -> None:
        self.fl2va_url = os.environ.get("H3_FL2VA_URL", "http://127.0.0.1:30010")
        self.ref2va_url = os.environ.get("H3_REF2VA_URL", "http://127.0.0.1:30011")
        self.upload_dir = Path(os.environ.get("H3_UPLOAD_DIR", str(UPLOAD_DIR)))
        self.output_dir = Path(os.environ.get("H3_OUTPUT_DIR", str(OUTPUT_DIR)))
        self.cors_origins = os.environ.get("H3_CORS_ORIGINS", "*")
        self.api_token = _load_api_token()

    def auth_headers(self) -> dict[str, str]:
        if not self.api_token:
            return {}
        return {"Authorization": f"Bearer {self.api_token}"}


settings = Settings()
settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.output_dir.mkdir(parents=True, exist_ok=True)

# Re-export for static UI mounting.
__all__ = ["ROOT", "settings"]
