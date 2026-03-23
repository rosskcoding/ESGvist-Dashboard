import pytest
from httpx import AsyncClient

from tests.conftest import TestSessionLocal
from app.db.models.data_point import DataPoint
from sqlalchemy import update


@pytest.fixture
async def ctx(client: AsyncClient) -> dict:
    await client.post(
        "/api/auth/register",
        json={"email": "a@t.com", "password": "password123", "full_name": "A"},
    )
    login = await client.post("/api/auth/login", json={"email": "a@t.com", "password": "password123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    org = await client.post("/api/organizations/setup", json={"name": "Co"}, headers=headers)
    headers["X-Organization-Id"] = str(org.json()["organization_id"])

    el = await client.post("/api/shared-elements", json={"code": "S1", "name": "S1"}, headers=headers)
    proj = await client.post("/api/projects", json={"name": "R"}, headers=headers)
    proj_id = proj.json()["id"]

    # Create 3 data points
    dp_ids = []
    for i in range(3):
        dp = await client.post(
            f"/api/projects/{proj_id}/data-points",
            json={"shared_element_id": el.json()["id"], "numeric_value": i * 100},
            headers=headers,
        )
        dp_ids.append(dp.json()["id"])

    # Set all to in_review
    async with TestSessionLocal() as session:
        await session.execute(
            update(DataPoint).where(DataPoint.id.in_(dp_ids)).values(status="in_review")
        )
        await session.commit()

    return {"headers": headers, "project_id": proj_id, "dp_ids": dp_ids}


# --- Batch Review ---
@pytest.mark.asyncio
async def test_batch_approve(client: AsyncClient, ctx: dict):
    resp = await client.post(
        "/api/review/batch-approve",
        json={"data_point_ids": ctx["dp_ids"], "comment": "All good"},
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["approved_count"] == 3


@pytest.mark.asyncio
async def test_batch_reject_requires_comment(client: AsyncClient, ctx: dict):
    resp = await client.post(
        "/api/review/batch-reject",
        json={"data_point_ids": ctx["dp_ids"]},
        headers=ctx["headers"],
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "REVIEW_COMMENT_REQUIRED"


@pytest.mark.asyncio
async def test_batch_reject_with_comment(client: AsyncClient, ctx: dict):
    resp = await client.post(
        "/api/review/batch-reject",
        json={"data_point_ids": ctx["dp_ids"], "comment": "Needs revision"},
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["rejected_count"] == 3


# --- Export / Readiness ---
@pytest.mark.asyncio
async def test_readiness_check_empty(client: AsyncClient, ctx: dict):
    resp = await client.get(f"/api/projects/{ctx['project_id']}/export/readiness")
    assert resp.status_code == 200
    data = resp.json()
    assert "ready" in data
    assert "completion_percent" in data
    assert "blocking_issues" in data


@pytest.mark.asyncio
async def test_publish_project(client: AsyncClient, ctx: dict):
    resp = await client.post(
        f"/api/projects/{ctx['project_id']}/publish",
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "published"


@pytest.mark.asyncio
async def test_publish_already_published(client: AsyncClient, ctx: dict):
    await client.post(f"/api/projects/{ctx['project_id']}/publish", headers=ctx["headers"])
    resp = await client.post(f"/api/projects/{ctx['project_id']}/publish", headers=ctx["headers"])
    assert resp.status_code == 409


# --- Audit Log ---
@pytest.mark.asyncio
async def test_audit_log(client: AsyncClient, ctx: dict):
    # Auth actions should have created audit entries
    resp = await client.get("/api/audit-log", headers=ctx["headers"])
    assert resp.status_code == 200
    assert "items" in resp.json()
