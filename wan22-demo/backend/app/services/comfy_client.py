from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import Settings, get_settings
from app.services.http_client import async_client


def _humanize_connect_error(exc: Exception, *, service: str, url: str) -> RuntimeError:
    msg = str(exc)
    if "All connection attempts failed" in msg or "Connection refused" in msg:
        return RuntimeError(
            f"{service} 未启动或不可达（{url}）。请先启动 ComfyUI，例如："
            f" deployment/start-all-gpu1.sh 或 deployment/start-instance.sh"
        )
    return RuntimeError(msg)


class ComfyClient:
    def __init__(self, settings: Settings | None = None, client: httpx.AsyncClient | None = None):
        self.settings = settings or get_settings()
        self._client = client
        self._owned = client is None

    async def __aenter__(self) -> "ComfyClient":
        if self._client is None:
            self._client = async_client(base_url=self.settings.comfyui_url, timeout=120.0)
            self._owned = True
        return self

    async def __aexit__(self, *args) -> None:
        if self._owned and self._client is not None:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("ComfyClient not started; use async with")
        return self._client

    @staticmethod
    def create_client_id() -> str:
        return str(uuid.uuid4())

    async def system_stats(self) -> dict:
        r = await self.client.get("/system_stats")
        r.raise_for_status()
        return r.json()

    async def upload_image(self, content: bytes, filename: str, subfolder: str = "", overwrite: bool = True) -> dict:
        return self._upload_image_local(content, filename, subfolder=subfolder, overwrite=overwrite)

    def _upload_image_local(
        self,
        content: bytes,
        filename: str,
        *,
        subfolder: str = "",
        overwrite: bool = True,
    ) -> dict:
        safe_name = Path(filename).name
        if not safe_name:
            raise RuntimeError("无效的文件名")
        dest_dir = self.settings.comfyui_root / "input"
        clean_subfolder = subfolder.strip("/\\")
        if clean_subfolder:
            dest_dir = dest_dir / clean_subfolder
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / safe_name
        if dest.exists() and not overwrite:
            stem = dest.stem
            suffix = dest.suffix
            for i in range(1, 1000):
                candidate = dest_dir / f"{stem}_{i}{suffix}"
                if not candidate.exists():
                    dest = candidate
                    safe_name = candidate.name
                    break
        dest.write_bytes(content)
        payload = {"name": safe_name, "subfolder": clean_subfolder, "type": "input"}
        name = f"{clean_subfolder}/{safe_name}" if clean_subfolder else safe_name
        return {"name": name, "raw": payload}

    async def _upload_image_http(self, content: bytes, filename: str, subfolder: str = "", overwrite: bool = True) -> dict:
        files = {"image": (filename, content)}
        data: dict[str, str] = {}
        if subfolder:
            data["subfolder"] = subfolder
        if overwrite:
            data["overwrite"] = "true"
        try:
            r = await self.client.post("/upload/image", files=files, data=data)
        except httpx.HTTPError as exc:
            raise _humanize_connect_error(exc, service="ComfyUI", url=self.settings.comfyui_url) from exc
        if r.status_code >= 400:
            raise RuntimeError(f"上传图片失败: {r.status_code} {r.text[:300]}")
        payload = r.json()
        name = f"{payload['subfolder']}/{payload['name']}" if payload.get("subfolder") else payload["name"]
        return {"name": name, "raw": payload}

    async def queue_prompt(self, prompt: dict, client_id: str) -> dict:
        try:
            r = await self.client.post("/prompt", json={"prompt": prompt, "client_id": client_id})
        except httpx.HTTPError as exc:
            raise _humanize_connect_error(exc, service="ComfyUI", url=self.settings.comfyui_url) from exc
        raw = r.text
        try:
            data = r.json() if raw else {}
        except Exception:
            data = {}
        if r.status_code >= 400:
            msg = (data.get("error") or {}).get("message") if isinstance(data.get("error"), dict) else None
            msg = msg or (raw[:300] if raw and not raw.startswith("{") else None) or f"提交失败: {r.status_code}"
            node_errors = data.get("node_errors")
            if node_errors:
                msg = f"{msg} | 节点错误: {node_errors}"
            raise RuntimeError(msg)
        return data

    async def get_history(self, prompt_id: str) -> dict:
        r = await self.client.get(f"/history/{prompt_id}")
        r.raise_for_status()
        return r.json()

    async def get_queue(self) -> dict:
        r = await self.client.get("/queue")
        r.raise_for_status()
        return r.json()

    async def interrupt(self) -> None:
        await self.client.post("/interrupt")

    def view_url(self, filename: str, subfolder: str = "", type_: str = "output") -> str:
        params = urlencode({"filename": filename, "subfolder": subfolder, "type": type_})
        return f"/v1/media/view?{params}"

    def comfy_view_url(self, filename: str, subfolder: str = "", type_: str = "output") -> str:
        params = urlencode({"filename": filename, "subfolder": subfolder, "type": type_})
        return f"{self.settings.comfyui_url.rstrip('/')}/view?{params}"

    @staticmethod
    def is_prompt_in_queue(queue_data: dict, prompt_id: str) -> dict[str, bool]:
        running = queue_data.get("queue_running") or []
        pending = queue_data.get("queue_pending") or []
        in_running = any(item[1] == prompt_id for item in running)
        in_pending = any(item[1] == prompt_id for item in pending)
        return {"inRunning": in_running, "inPending": in_pending, "inQueue": in_running or in_pending}

    @staticmethod
    def get_queue_position(queue_data: dict, prompt_id: str) -> int:
        pending = queue_data.get("queue_pending") or []
        for i, item in enumerate(pending):
            if item[1] == prompt_id:
                return i + 1
        return 0


async def get_comfy_client() -> ComfyClient:
    return ComfyClient()
