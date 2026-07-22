from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".mkv"}
FILENAME_TS_RE = re.compile(r"-(\d{8})-(\d{4})_")


def parse_filename_timestamp(filename: str) -> int:
    """Parse ComfyUI-style timestamp from filename (e.g. ...-20260717-1441_)."""
    match = FILENAME_TS_RE.search(filename)
    if not match:
        return 0
    ymd, hm = match.groups()
    try:
        dt = datetime(
            int(ymd[:4]),
            int(ymd[4:6]),
            int(ymd[6:8]),
            int(hm[:2]),
            int(hm[2:4]),
        )
        return int(dt.timestamp() * 1000)
    except ValueError:
        return 0


def infer_mode_from_filename(filename: str) -> str:
    lower = filename.lower()
    if "ltx" in lower:
        if "i2v" in lower or "img" in lower:
            return "ltx-i2v-import"
        return "ltx-t2v-import"
    if "i2v" in lower or "img2vid" in lower:
        return "wan-i2v-import"
    if "flf2v" in lower:
        return "wan-flf2v-import"
    if "t2v" in lower or "text2vid" in lower:
        return "wan-t2v-import"
    return "comfyui-import"


def format_history_time(ts_ms: int) -> str:
    if ts_ms <= 0:
        return ""
    return datetime.fromtimestamp(ts_ms / 1000).strftime("%m/%d %H:%M:%S")


def build_view_url(filename: str, *, subfolder: str = "video") -> str:
    params = urlencode({"filename": filename, "subfolder": subfolder, "type": "output"})
    return f"/v1/media/view?{params}"


def list_recent_videos(video_dir: Path, *, limit: int = 50) -> dict:
    """Scan ComfyUI output/video, sort by filename timestamp (mtime fallback), return newest N."""
    if not video_dir.is_dir():
        return {
            "videos": [],
            "scannedDir": str(video_dir),
            "totalFiles": 0,
            "returned": 0,
        }

    entries: list[tuple[int, str, float]] = []
    for path in video_dir.iterdir():
        if not path.is_file():
            continue
        if path.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        filename = path.name
        created_at = parse_filename_timestamp(filename)
        mtime_ms = path.stat().st_mtime * 1000
        if created_at <= 0:
            created_at = int(mtime_ms)
        entries.append((created_at, filename, mtime_ms))

    entries.sort(key=lambda row: (row[0], row[2], row[1]), reverse=True)
    selected = entries[:limit]

    videos = []
    for created_at, filename, _ in selected:
        videos.append(
            {
                "filename": filename,
                "subfolder": "video",
                "type": "output",
                "kind": "video",
                "url": build_view_url(filename),
                "mode": infer_mode_from_filename(filename),
                "createdAt": created_at,
                "time": format_history_time(created_at),
                "label": "ComfyUI 导入",
                "source": "comfyui_dir",
            }
        )

    return {
        "videos": videos,
        "scannedDir": str(video_dir.resolve()),
        "totalFiles": len(entries),
        "returned": len(videos),
    }
