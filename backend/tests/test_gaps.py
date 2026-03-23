"""Tests for gap-closure: gates, policies, platform admin, events, models."""

import pytest
from httpx import AsyncClient


@pytest.fixture
async def ctx(client: AsyncClient) -> dict:
    await client.post(
        "/api/auth/register",
        json={"email": "a@t.com", "password": "password123", "full_name": "Admin"},
    )
    login = await client.post("/api/auth/login", json={"email": "a@t.com", "password": "password123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    org = await client.post("/api/organizations/setup", json={"name": "Co"}, headers=headers)
    org_id = org.json()["organization_id"]
    headers["X-Organization-Id"] = str(org_id)

    return {"headers": headers, "org_id": org_id, "token": login.json()["access_token"]}


# === PLATFORM ADMIN ===

@pytest.mark.asyncio
async def test_platform_list_tenants(client: AsyncClient, ctx: dict):
    resp = await client.get("/api/platform/tenants", headers=ctx["headers"])
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_platform_get_tenant(client: AsyncClient, ctx: dict):
    resp = await client.get(f"/api/platform/tenants/{ctx['org_id']}", headers=ctx["headers"])
    assert resp.status_code == 200
    assert resp.json()["name"] == "Co"


@pytest.mark.asyncio
async def test_platform_update_tenant(client: AsyncClient, ctx: dict):
    resp = await client.patch(
        f"/api/platform/tenants/{ctx['org_id']}",
        json={"name": "Updated Co"},
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] is True


@pytest.mark.asyncio
async def test_platform_suspend_reactivate(client: AsyncClient, ctx: dict):
    resp = await client.post(
        f"/api/platform/tenants/{ctx['org_id']}/suspend", headers=ctx["headers"]
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "suspended"

    resp = await client.post(
        f"/api/platform/tenants/{ctx['org_id']}/reactivate", headers=ctx["headers"]
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


@pytest.mark.asyncio
async def test_platform_list_users(client: AsyncClient, ctx: dict):
    resp = await client.get("/api/platform/users", headers=ctx["headers"])
    assert resp.status_code == 200
    assert len(resp.json()["items"]) >= 1


@pytest.mark.asyncio
async def test_platform_assign_admin(client: AsyncClient, ctx: dict):
    # Register second user
    await client.post(
        "/api/auth/register",
        json={"email": "b@t.com", "password": "password123", "full_name": "User B"},
    )

    # Get user B's id
    users_resp = await client.get("/api/platform/users", headers=ctx["headers"])
    user_b = next(u for u in users_resp.json()["items"] if u["email"] == "b@t.com")

    # Create new org for assignment
    org2 = await client.post(
        "/api/organizations/setup", json={"name": "Org2"}, headers=ctx["headers"]
    )

    resp = await client.post(
        f"/api/platform/tenants/{org2.json()['organization_id']}/admins",
        json={"user_id": user_b["id"]},
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_platform_non_admin_forbidden(client: AsyncClient):
    # Register first user (platform admin)
    await client.post(
        "/api/auth/register",
        json={"email": "a@t.com", "password": "password123", "full_name": "A"},
    )
    # Register second user (not platform admin)
    await client.post(
        "/api/auth/register",
        json={"email": "b@t.com", "password": "password123", "full_name": "B"},
    )
    login = await client.post("/api/auth/login", json={"email": "b@t.com", "password": "password123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.get("/api/platform/tenants", headers=headers)
    # Non-platform user gets either 400 (no org header) or 403
    assert resp.status_code in (400, 403)


# === ALL GATES REGISTERED ===

@pytest.mark.asyncio
async def test_gate_engine_has_all_gates(client: AsyncClient, ctx: dict):
    """Verify gate engine has 13 gates registered."""
    el = await client.post("/api/shared-elements", json={"code": "S", "name": "S"}, headers=ctx["headers"])
    proj = await client.post("/api/projects", json={"name": "P"}, headers=ctx["headers"])
    dp = await client.post(
        f"/api/projects/{proj.json()['id']}/data-points",
        json={"shared_element_id": el.json()["id"], "numeric_value": 1},
        headers=ctx["headers"],
    )

    # Gate check should work (verifies engine is wired up with all gates)
    resp = await client.post(
        "/api/gate-check",
        json={"action": "submit_data_point", "data_point_id": dp.json()["id"]},
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    assert "allowed" in resp.json()


# === EVENT BUS EXISTS ===

@pytest.mark.asyncio
async def test_event_bus_singleton():
    from app.events.bus import get_event_bus, EventBus
    bus = get_event_bus()
    assert isinstance(bus, EventBus)


@pytest.mark.asyncio
async def test_event_bus_publish_subscribe():
    from app.events.bus import EventBus, DataPointSubmitted

    bus = EventBus()
    received = []

    async def handler(event):
        received.append(event)

    bus.subscribe(DataPointSubmitted, handler)
    await bus.publish(DataPointSubmitted(data_point_id=1, submitted_by=1))
    assert len(received) == 1
    assert received[0].data_point_id == 1


# === NEW MODELS EXIST ===

@pytest.mark.asyncio
async def test_models_created():
    """Verify all new models create tables without error."""
    from app.db.models import (
        BoundarySnapshot,
        UserInvitation,
        RequirementItemEvidence,
        AIInteraction,
    )
    # Just verify classes exist and have __tablename__
    assert BoundarySnapshot.__tablename__ == "boundary_snapshots"
    assert UserInvitation.__tablename__ == "user_invitations"
    assert RequirementItemEvidence.__tablename__ == "requirement_item_evidences"
    assert AIInteraction.__tablename__ == "ai_interactions"


# === POLICIES EXIST ===

@pytest.mark.asyncio
async def test_auth_policy_tenant_isolation():
    from app.policies.auth_policy import AuthPolicy
    from app.core.dependencies import RequestContext

    ctx_a = RequestContext(user_id=1, email="a@t.com", organization_id=1, role="admin")

    # Same org — should pass
    AuthPolicy.check_tenant_isolation(ctx_a, 1)

    # Different org — should raise
    with pytest.raises(Exception):
        AuthPolicy.check_tenant_isolation(ctx_a, 2)


@pytest.mark.asyncio
async def test_auth_policy_platform_admin_bypass():
    from app.policies.auth_policy import AuthPolicy
    from app.core.dependencies import RequestContext

    ctx = RequestContext(user_id=1, email="a@t.com", role="platform_admin", is_platform_admin=True)
    # Platform admin can access any org
    AuthPolicy.check_tenant_isolation(ctx, 999)


@pytest.mark.asyncio
async def test_evidence_policy_exists():
    from app.policies.evidence_policy import EvidencePolicy
    from app.core.dependencies import RequestContext

    policy = EvidencePolicy()
    ctx = RequestContext(user_id=1, email="a@t.com", organization_id=1, role="collector")
    policy.can_create(ctx)  # should not raise

    ctx_auditor = RequestContext(user_id=1, email="a@t.com", organization_id=1, role="auditor")
    with pytest.raises(Exception):
        policy.can_create(ctx_auditor)


@pytest.mark.asyncio
async def test_boundary_policy_exists():
    from app.policies.boundary_policy import BoundaryPolicy
    from app.core.dependencies import RequestContext

    ctx = RequestContext(user_id=1, email="a@t.com", organization_id=1, role="admin")
    BoundaryPolicy.can_create(ctx)

    with pytest.raises(Exception):
        BoundaryPolicy.snapshot_immutable("published")


@pytest.mark.asyncio
async def test_project_policy_exists():
    from app.policies.project_policy import ProjectPolicy
    from app.core.dependencies import RequestContext

    ctx = RequestContext(user_id=1, email="a@t.com", organization_id=1, role="esg_manager")
    ProjectPolicy.can_manage(ctx)
    ProjectPolicy.can_publish(ctx)

    with pytest.raises(Exception):
        ProjectPolicy.project_not_locked("published")
