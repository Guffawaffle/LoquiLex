import time

import pytest
from httpx import AsyncClient

from loquilex.api import server


@pytest.mark.asyncio
async def test_clear_cache_no_auth_client():
    # Ensure admin token is set for this test (set on module to avoid import-time env issues)
    server._ADMIN_TOKEN = "testtoken"

    async with AsyncClient(app=server.app, base_url="http://test") as ac:
        # Without auth header expect 403
        r = await ac.post("/admin/cache/clear")
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_clear_cache_with_auth():
    server._ADMIN_TOKEN = "testtoken"

    # Prime the in-memory cache
    server._hw_snapshot_cache = {"foo": "bar"}
    server._hw_snapshot_cache_ts = time.time()

    async with AsyncClient(app=server.app, base_url="http://test") as ac:
        headers = {"Authorization": "Bearer testtoken"}
        r = await ac.post("/admin/cache/clear", headers=headers)
        assert r.status_code == 200
        j = r.json()
        assert j.get("ok") is True
        assert j.get("cleared") is True
        assert j.get("prior_cache_present") is True

    # Ensure cache cleared
    assert server._hw_snapshot_cache is None
