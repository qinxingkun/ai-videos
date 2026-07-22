from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.workflow_builder import build_ltx23_t2v, load_workflow

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / "workflows"
client = TestClient(app)


def test_root_and_health():
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert "videos" in body
    assert "images" in body
    h = client.get("/health")
    assert h.status_code == 200
    assert h.json()["ok"] is True


def test_t2i_requires_prompt():
    r = client.post("/v1/images/t2i", json={"prompt": ""})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_generate_t2i_mocked_provider(monkeypatch):
    from app.services import image as image_service

    async def fake_call(body):
        return b"\x89PNG\r\n\x1a\n"

    monkeypatch.setattr(image_service, "_call_provider", fake_call)

    r = client.post(
        "/v1/images/t2i",
        json={"prompt": "a cat", "width": 1328, "height": 1328, "steps": 4, "turbo": True},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["task_id"]
    assert body["status"] == "queued"


def test_list_characters():
    r = client.get("/v1/characters")
    assert r.status_code == 200
    assert isinstance(r.json()["characters"], list)


def test_recent_videos_endpoint(monkeypatch, tmp_path: Path):
    (tmp_path / "wan2.2_t2v_foo-20260717-1430_00001_.mp4").write_bytes(b"x")

    monkeypatch.setattr(
        "app.api.media.get_settings",
        lambda: type("S", (), {"video_dir": tmp_path})(),
    )
    r = client.get("/v1/media/recent-videos?limit=3")
    assert r.status_code == 200
    body = r.json()
    assert body["returned"] == 1
    assert body["videos"][0]["filename"].endswith(".mp4")


def test_t2v_requires_prompt():
    r = client.post("/v1/videos/t2v", json={"engine": "ltx"})
    assert r.status_code == 422


def test_ltx_t2v_workflow_inject():
    path = WORKFLOWS / "ltx23_t2v.api.json"
    if not path.exists():
        pytest.skip("workflow missing")
    base = load_workflow(path)
    built = build_ltx23_t2v(
        base,
        {
            "positivePrompt": "hello world",
            "seed": 42,
            "width": 768,
            "height": 512,
            "length": 121,
            "fps": 24,
        },
    )
    g = built["graph"]
    assert g["305"]["inputs"]["text"] == "hello world"
    assert g["279"]["inputs"]["noise_seed"] == 42


@pytest.mark.asyncio
async def test_generate_t2v_mocked_comfy(monkeypatch):
    from app.services import video as video_service

    class FakeComfy:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        @staticmethod
        def create_client_id():
            return "cid"

        async def queue_prompt(self, prompt, client_id):
            assert "305" in prompt or len(prompt) > 0
            return {"prompt_id": "pid-1"}

    monkeypatch.setattr(video_service, "ComfyClient", FakeComfy)
    out = await video_service.generate_video_t2v({"prompt": "sunset", "engine": "ltx"})
    assert out["task_id"].startswith("task_")
    assert out["prompt_id"] == "pid-1"
    assert out["status"] == "queued"


@pytest.mark.asyncio
async def test_get_video_task_completed(monkeypatch):
    from app.services.task_store import task_store
    from app.services import video as video_service

    task_id = task_store.create("pid-done", "cid", meta={})

    class FakeComfy:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def get_history(self, prompt_id):
            return {
                prompt_id: {
                    "outputs": {
                        "1": {
                            "videos": [{"filename": "a.mp4", "subfolder": "video", "type": "output"}]
                        }
                    }
                }
            }

        async def get_queue(self):
            return {"queue_running": [], "queue_pending": []}

        def view_url(self, filename, subfolder="", type_="output"):
            return f"/v1/media/view?filename={filename}"

        def comfy_view_url(self, filename, subfolder="", type_="output"):
            return f"http://comfy/view?filename={filename}"

    monkeypatch.setattr(video_service, "ComfyClient", FakeComfy)
    out = await video_service.get_video_task({"task_id": task_id})
    assert out["status"] == "completed"
    assert out["media"][0]["filename"] == "a.mp4"


def test_map_args_drops_none_fps():
    from app.services.video import _map_args

    params = _map_args({"prompt": "x", "engine": "ltx"})
    assert "fps" not in params
    assert params["positivePrompt"] == "x"


def test_http_t2v_mocked(monkeypatch):
    from app.services import video as video_service

    async def fake_t2v(args):
        return {"task_id": "task_x", "prompt_id": "p", "status": "queued", "client_id": "c", "meta": {}}

    monkeypatch.setattr(video_service, "generate_video_t2v", fake_t2v)
    r = client.post("/v1/videos/t2v", json={"prompt": "cat", "engine": "ltx"})
    assert r.status_code == 200
    assert r.json()["task_id"] == "task_x"
