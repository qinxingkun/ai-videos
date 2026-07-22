from __future__ import annotations

import httpx


def async_client(**kwargs) -> httpx.AsyncClient:
    """Local-service httpx client; ignores HTTP_PROXY/HTTPS_PROXY."""
    return httpx.AsyncClient(trust_env=False, **kwargs)
