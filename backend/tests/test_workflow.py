import pytest
from httpx import AsyncClient


@pytest.fixture
async def ctx(client: AsyncClient) -> dict:
    """Full setup: register, org, project, shared element, data point (draft)."""
    await client.post(
        "/api/auth/register",
        json={"email": "admin@test.com", "password": "password123", "full_name": "Admin"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": "admin@test.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    org = await client.post("/api/organizations/setup", json={"name": "Co"}, headers=headers)
    headers["X-Organization-Id"] = str(org.json()["organization_id"])

    proj = await client.post("/api/projects", json={"name": "Report"}, headers=headers)
    el = await client.post(
        "/api/shared-elements", json={"code": "S1", "name": "Scope 1"}, headers=headers
    )
    dp = await client.post(
        f"/api/projects/{proj.json()['id']}/data-points",
        json={"shared_element_id": el.json()["id"], "numeric_value": 100},
        headers=headers,
    )

    return {"headers": headers, "dp_id": dp.json()["id"], "project_id": proj.json()["id"]}


# --- Workflow transitions ---
@pytest.mark.asyncio
async def test_submit_draft(client: AsyncClient, ctx: dict):
    resp = await client.post(
        f"/api/data-points/{ctx['dp_id']}/submit", headers=ctx["headers"]
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "submitted"


@pytest.mark.asyncio
async def test_approve_needs_in_review_status(client: AsyncClient, ctx: dict):
    # Try to approve draft directly → should fail (no transition draft→approved)
    resp = await client.post(
        f"/api/data-points/{ctx['dp_id']}/approve", headers=ctx["headers"]
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_WORKFLOW_TRANSITION"


@pytest.mark.asyncio
async def test_full_workflow_submit_to_approve(client: AsyncClient, ctx: dict):
    # Submit
    await client.post(f"/api/data-points/{ctx['dp_id']}/submit", headers=ctx["headers"])

    # Manually set to in_review (simulating auto-transition)
    from tests.conftest import TestSessionLocal
    from app.db.models.data_point import DataPoint
    from sqlalchemy import update

    async with TestSessionLocal() as session:
        await session.execute(
            update(DataPoint).where(DataPoint.id == ctx["dp_id"]).values(status="in_review")
        )
        await session.commit()

    # Approve
    resp = await client.post(
        f"/api/data-points/{ctx['dp_id']}/approve",
        json={"comment": "Looks good"},
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_reject_requires_comment(client: AsyncClient, ctx: dict):
    await client.post(f"/api/data-points/{ctx['dp_id']}/submit", headers=ctx["headers"])

    async with (await _set_status(ctx["dp_id"], "in_review")):
        pass

    resp = await client.post(
        f"/api/data-points/{ctx['dp_id']}/reject",
        headers=ctx["headers"],
        # No comment!
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "REVIEW_COMMENT_REQUIRED"


@pytest.mark.asyncio
async def test_reject_with_comment(client: AsyncClient, ctx: dict):
    await client.post(f"/api/data-points/{ctx['dp_id']}/submit", headers=ctx["headers"])

    async with (await _set_status(ctx["dp_id"], "in_review")):
        pass

    resp = await client.post(
        f"/api/data-points/{ctx['dp_id']}/reject",
        json={"comment": "Value seems wrong"},
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_rollback_approved_to_draft(client: AsyncClient, ctx: dict):
    async with (await _set_status(ctx["dp_id"], "approved")):
        pass

    resp = await client.post(
        f"/api/data-points/{ctx['dp_id']}/rollback",
        json={"comment": "Need to correct value"},
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "draft"


@pytest.mark.asyncio
async def test_rollback_requires_comment(client: AsyncClient, ctx: dict):
    async with (await _set_status(ctx["dp_id"], "approved")):
        pass

    resp = await client.post(
        f"/api/data-points/{ctx['dp_id']}/rollback",
        headers=ctx["headers"],
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "REVIEW_COMMENT_REQUIRED"


@pytest.mark.asyncio
async def test_invalid_transition(client: AsyncClient, ctx: dict):
    # submitted → draft is not allowed
    await client.post(f"/api/data-points/{ctx['dp_id']}/submit", headers=ctx["headers"])

    resp = await client.post(
        f"/api/data-points/{ctx['dp_id']}/rollback",
        json={"comment": "test"},
        headers=ctx["headers"],
    )
    assert resp.status_code == 422


# --- Gate Check ---
@pytest.mark.asyncio
async def test_gate_check_allowed(client: AsyncClient, ctx: dict):
    resp = await client.post(
        "/api/gate-check",
        json={"action": "submit_data_point", "data_point_id": ctx["dp_id"]},
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["allowed"] is True


@pytest.mark.asyncio
async def test_gate_check_blocked(client: AsyncClient, ctx: dict):
    resp = await client.post(
        "/api/gate-check",
        json={"action": "approve_data_point", "data_point_id": ctx["dp_id"]},
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["allowed"] is False
    assert len(resp.json()["failedGates"]) > 0


# Helper
async def _set_status(dp_id, status):
    from contextlib import asynccontextmanager
    from tests.conftest import TestSessionLocal
    from app.db.models.data_point import DataPoint
    from sqlalchemy import update

    @asynccontextmanager
    async def _ctx():
        async with TestSessionLocal() as session:
            await session.execute(
                update(DataPoint).where(DataPoint.id == dp_id).values(status=status)
            )
            await session.commit()
        yield

    return _ctx()
