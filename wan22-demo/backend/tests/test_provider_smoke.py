from __future__ import annotations

import os
from urllib.parse import urlsplit, urlunsplit

import httpx
import pytest

from app.config import Settings


pytestmark = pytest.mark.smoke_real


def _health_url(endpoint: str) -> str:
    split = urlsplit(endpoint)
    return urlunsplit((split.scheme, split.netloc, "/health", "", ""))


@pytest.mark.skipif(
    os.getenv("RUN_REAL_DUB_SMOKE") != "1",
    reason="set RUN_REAL_DUB_SMOKE=1 to probe live GPU providers",
)
def test_live_dubbing_provider_health():
    settings = Settings()
    endpoints = [
        settings.cosyvoice_url,
        settings.latentsync_url,
        settings.asr_qa_url,
        settings.syncnet_qa_url,
    ]
    assert all(endpoints), "all production dubbing endpoints must be configured"
    with httpx.Client(timeout=10.0) as client:
        for endpoint in set(endpoints):
            response = client.get(_health_url(endpoint))
            response.raise_for_status()
            assert response.json()["ok"] is True
