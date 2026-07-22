from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    comfyui_url: str = "http://127.0.0.1:8188"
    comfyui_root: Path = PROJECT_ROOT.parent / "ComfyUI"
    host: str = "0.0.0.0"
    port: int = 8190
    workflows_dir: Path = BACKEND_ROOT / "workflows"
    project_root: Path = PROJECT_ROOT
    characters_file: Path = BACKEND_ROOT / "data" / "characters.json"
    task_timeout_ms: int = 7_200_000
    cors_origins: list[str] = ["*"]
    cosyvoice_url: str | None = None
    qwen_image_url: str | None = "http://127.0.0.1:8192"
    qwen_image_model_dir: Path = Path("/mnt/ddr1/ai-models/models-download/qwen/Qwen-Image-2512")
    cosyvoice_cli: str | None = None
    asr_qa_url: str | None = None
    tts_provider_mode: str = "required"
    latentsync_url: str | None = None
    latentsync_cli: str | None = None
    syncnet_qa_url: str | None = None
    lipsync_provider_mode: str = "required"
    provider_timeout_sec: float = 600.0
    visual_master_rife_enabled: bool = True
    dubbing_sessions_dir: Path = BACKEND_ROOT / "data" / "dubbing_sessions"
    dubbing_session_ttl_hours: int = 72
    insightface_root: Path = PROJECT_ROOT.parent / "LatentSync" / "checkpoints" / "auxiliary"
    face_binding_threshold: float = 0.35
    face_binding_margin: float = 0.05
    face_track_min_frames: int = 3
    face_track_min_size: int = 32
    face_track_max_gap_frames: int = 8
    face_track_reid_threshold: float = 0.38
    face_track_assignment_cost: float = 0.72
    face_visible_ratio_min: float = 0.65
    asr_qa_similarity_min: float = 0.70
    syncnet_confidence_min: float = 3.0
    syncnet_offset_max_frames: int = 1
    dub_required_rife: bool = True

    @property
    def video_dir(self) -> Path:
        return self.comfyui_root / "output" / "video"

    @property
    def input_dir(self) -> Path:
        return self.comfyui_root / "input"


@lru_cache
def get_settings() -> Settings:
    return Settings()
