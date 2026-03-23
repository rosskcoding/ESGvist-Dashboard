import pytest
from httpx import AsyncClient

from tests.conftest import TestSessionLocal
from app.db.models.notification import Notification


@pytest.fixture
async def ctx(client: AsyncClient) -> dict:
    await client.post(
        "/api/auth/register",
        json={"email": "a@t.com", "password": "password123", "full_name": "A"},
    )
    login = await client.post("/api/auth/login", json={"email": "a@t.com", "password": "password123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    org = await client.post("/api/organizations/setup", json={"name": "Co"}, headers=headers)
    org_id = org.json()["organization_id"]

    # Create notifications directly in DB
    async with TestSessionLocal() as session:
        for i in range(3):
            session.add(Notification(
                organization_id=org_id,
                user_id=1,
                type="test_event",
                title=f"Test {i}",
                message=f"Message {i}",
                severity="info",
            ))
        await session.commit()

    return {"headers": headers, "org_id": org_id}


@pytest.mark.asyncio
async def test_list_notifications(client: AsyncClient, ctx: dict):
    resp = await client.get("/api/notifications", headers=ctx["headers"])
    assert resp.status_code == 200
    assert resp.json()["total"] == 3


@pytest.mark.asyncio
async def test_unread_count(client: AsyncClient, ctx: dict):
    resp = await client.get("/api/notifications/unread-count", headers=ctx["headers"])
    assert resp.status_code == 200
    assert resp.json()["unread_count"] == 3


@pytest.mark.asyncio
async def test_mark_read(client: AsyncClient, ctx: dict):
    # Get first notification
    list_resp = await client.get("/api/notifications", headers=ctx["headers"])
    nid = list_resp.json()["items"][0]["id"]

    resp = await client.patch(f"/api/notifications/{nid}/read", headers=ctx["headers"])
    assert resp.status_code == 200

    # Unread count should decrease
    count = await client.get("/api/notifications/unread-count", headers=ctx["headers"])
    assert count.json()["unread_count"] == 2


@pytest.mark.asyncio
async def test_mark_all_read(client: AsyncClient, ctx: dict):
    resp = await client.post("/api/notifications/read-all", headers=ctx["headers"])
    assert resp.status_code == 200

    count = await client.get("/api/notifications/unread-count", headers=ctx["headers"])
    assert count.json()["unread_count"] == 0
