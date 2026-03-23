import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["checks"]["api"] == "ok"
    assert data["version"] == "0.1.0"
    assert isinstance(data["uptime"], int)


@pytest.mark.asyncio
async def test_health_redis_uses_check_result(monkeypatch, client: AsyncClient):
    async def fake_check():
        return "ok"

    monkeypatch.setattr("app.api.routes.health._check_redis", fake_check)
    resp = await client.get("/api/health/redis")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"
    assert resp.json()["checks"]["redis"] == "ok"


@pytest.mark.asyncio
async def test_health_storage_uses_check_result(monkeypatch, client: AsyncClient):
    async def fake_check():
        return "error"

    monkeypatch.setattr("app.api.routes.health._check_storage", fake_check)
    resp = await client.get("/api/health/storage")
    assert resp.status_code == 200
    assert resp.json()["status"] == "unhealthy"
    assert resp.json()["checks"]["storage"] == "error"
