import pytest
from httpx import AsyncClient

from app.db.models.audit_log import AuditLog
from app.db.models.boundary import BoundaryMembership
from tests.conftest import TestSessionLocal


@pytest.fixture
async def admin_headers(client: AsyncClient) -> dict:
    await client.post(
        "/api/auth/register",
        json={"email": "admin@test.com", "password": "password123", "full_name": "Admin"},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"email": "admin@test.com", "password": "password123"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
async def org_setup(client: AsyncClient, admin_headers: dict) -> dict:
    """Setup org and return org_id + root_entity_id + headers with org context."""
    resp = await client.post(
        "/api/organizations/setup",
        json={"name": "KazEnergy Group", "country": "KZ", "industry": "oil_gas"},
        headers=admin_headers,
    )
    data = resp.json()
    headers = {**admin_headers, "X-Organization-Id": str(data["organization_id"])}
    return {
        "org_id": data["organization_id"],
        "root_id": data["root_entity_id"],
        "boundary_id": data["boundary_id"],
        "headers": headers,
    }


# --- Org Setup ---
@pytest.mark.asyncio
async def test_org_setup_creates_org_and_root(client: AsyncClient, admin_headers: dict):
    resp = await client.post(
        "/api/organizations/setup",
        json={"name": "TestCo", "country": "US"},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "organization_id" in data
    assert "root_entity_id" in data


@pytest.mark.asyncio
async def test_org_setup_creates_default_boundary_membership(client: AsyncClient, admin_headers: dict):
    resp = await client.post(
        "/api/organizations/setup",
        json={"name": "BoundaryCo", "country": "US"},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    data = resp.json()

    async with TestSessionLocal() as session:
        from sqlalchemy import select

        membership_result = await session.execute(
            select(BoundaryMembership).where(
                BoundaryMembership.boundary_definition_id == data["boundary_id"],
                BoundaryMembership.entity_id == data["root_entity_id"],
            )
        )
        membership = membership_result.scalar_one_or_none()

    assert membership is not None
    assert membership.included is True
    assert membership.entity_id == data["root_entity_id"]


@pytest.mark.asyncio
async def test_org_setup_assigns_admin_role(client: AsyncClient, admin_headers: dict):
    resp = await client.post(
        "/api/organizations/setup",
        json={"name": "TestCo"},
        headers=admin_headers,
    )
    org_id = resp.json()["organization_id"]

    # Check user has admin role in new org
    me = await client.get("/api/auth/me", headers=admin_headers)
    roles = me.json()["roles"]
    org_roles = [r for r in roles if r["scope_id"] == org_id]
    assert len(org_roles) == 1
    assert org_roles[0]["role"] == "admin"


@pytest.mark.asyncio
async def test_org_setup_allows_unaffiliated_user_without_org_header(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={"email": "platform@test.com", "password": "password123", "full_name": "Platform"},
    )
    await client.post(
        "/api/auth/register",
        json={"email": "founder@test.com", "password": "password123", "full_name": "Founder"},
    )

    login = await client.post(
        "/api/auth/login",
        json={"email": "founder@test.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    setup = await client.post(
        "/api/organizations/setup",
        json={"name": "Founder Org", "country": "GB", "industry": "technology"},
        headers=headers,
    )
    assert setup.status_code == 201

    me = await client.get("/api/auth/me", headers=headers)
    org_roles = [
        role
        for role in me.json()["roles"]
        if role["scope_id"] == setup.json()["organization_id"]
    ]
    assert len(org_roles) == 1
    assert org_roles[0]["role"] == "admin"


@pytest.mark.asyncio
async def test_org_setup_persists_defaults_children_and_invites(client: AsyncClient, admin_headers: dict):
    resp = await client.post(
        "/api/organizations/setup",
        json={
            "name": "Defaults Co",
            "legal_name": "Defaults Holdings LLC",
            "registration_number": "REG-001",
            "country": "DE",
            "jurisdiction": "Germany",
            "industry": "manufacturing",
            "reporting_year": 2027,
            "standards": ["GRI", "IFRS_S2"],
            "consolidation_approach": "operational_control",
            "ghg_scope_approach": "market_based",
            "subsidiaries": [
                {
                    "name": "Defaults Plant",
                    "entity_type": "legal_entity",
                    "country": "DE",
                    "ownership_percent": 100,
                },
                {
                    "name": "JV North",
                    "entity_type": "joint_venture",
                    "country": "FR",
                    "ownership_percent": 50,
                },
            ],
            "invite_users": [
                {
                    "email": "esg.defaults@example.com",
                    "role": "esg_manager",
                }
            ],
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["created_entities"] == 3
    assert data["invited_users"] == 1
    assert data["next_step"] == "/dashboard"

    headers = {**admin_headers, "X-Organization-Id": str(data["organization_id"])}

    org_settings = await client.get("/api/auth/me/organization", headers=headers)
    assert org_settings.status_code == 200
    assert org_settings.json()["legal_name"] == "Defaults Holdings LLC"
    assert org_settings.json()["registration_number"] == "REG-001"
    assert org_settings.json()["jurisdiction"] == "Germany"
    assert org_settings.json()["currency"] == "EUR"
    assert org_settings.json()["reporting_year"] == 2027
    assert org_settings.json()["default_standards"] == ["GRI", "IFRS_S2"]
    assert org_settings.json()["consolidation_approach"] == "operational_control"
    assert org_settings.json()["ghg_scope_approach"] == "market_based"

    entities = await client.get("/api/entities", headers=headers)
    assert entities.status_code == 200
    assert entities.json()["total"] == 3

    invitations = await client.get("/api/invitations", headers=headers)
    assert invitations.status_code == 200
    assert len(invitations.json()) == 1
    assert invitations.json()[0]["email"] == "esg.defaults@example.com"

    async with TestSessionLocal() as session:
        from sqlalchemy import select

        audit_logs = (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.organization_id == data["organization_id"],
                    AuditLog.action.in_(["create_entity", "create_boundary"]),
                )
            )
        ).scalars().all()

    assert len(audit_logs) >= 4


# --- Entities ---
@pytest.mark.asyncio
async def test_create_entity(client: AsyncClient, org_setup: dict):
    resp = await client.post(
        "/api/entities",
        json={"name": "Subsidiary A", "entity_type": "legal_entity", "country": "KZ"},
        headers=org_setup["headers"],
    )
    assert resp.status_code == 201
    assert resp.json()["entity_type"] == "legal_entity"
    assert resp.json()["organization_id"] == org_setup["org_id"]

    async with TestSessionLocal() as session:
        from sqlalchemy import select

        membership_result = await session.execute(
            select(BoundaryMembership).where(
                BoundaryMembership.boundary_definition_id == org_setup["boundary_id"],
                BoundaryMembership.entity_id == resp.json()["id"],
            )
        )
        membership = membership_result.scalar_one_or_none()

    assert membership is not None
    assert membership.included is True


@pytest.mark.asyncio
async def test_list_entities(client: AsyncClient, org_setup: dict):
    for i in range(3):
        await client.post(
            "/api/entities",
            json={"name": f"Sub {i}", "entity_type": "legal_entity"},
            headers=org_setup["headers"],
        )

    resp = await client.get("/api/entities", headers=org_setup["headers"])
    assert resp.status_code == 200
    # Root entity + 3 subsidiaries = 4
    assert resp.json()["total"] == 4


# --- Ownership ---
@pytest.mark.asyncio
async def test_create_ownership(client: AsyncClient, org_setup: dict):
    child = await client.post(
        "/api/entities",
        json={"name": "Child", "entity_type": "legal_entity"},
        headers=org_setup["headers"],
    )
    child_id = child.json()["id"]

    resp = await client.post(
        "/api/ownership-links",
        json={
            "parent_entity_id": org_setup["root_id"],
            "child_entity_id": child_id,
            "ownership_percent": 100,
        },
        headers=org_setup["headers"],
    )
    assert resp.status_code == 201
    assert resp.json()["ownership_percent"] == 100


@pytest.mark.asyncio
async def test_self_ownership_rejected(client: AsyncClient, org_setup: dict):
    resp = await client.post(
        "/api/ownership-links",
        json={
            "parent_entity_id": org_setup["root_id"],
            "child_entity_id": org_setup["root_id"],
            "ownership_percent": 100,
        },
        headers=org_setup["headers"],
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "SELF_OWNERSHIP_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_ownership_exceeds_100(client: AsyncClient, org_setup: dict):
    child = await client.post(
        "/api/entities",
        json={"name": "JV", "entity_type": "joint_venture"},
        headers=org_setup["headers"],
    )
    child_id = child.json()["id"]

    await client.post(
        "/api/ownership-links",
        json={"parent_entity_id": org_setup["root_id"], "child_entity_id": child_id, "ownership_percent": 60},
        headers=org_setup["headers"],
    )

    # Create another owner
    owner2 = await client.post(
        "/api/entities",
        json={"name": "Partner", "entity_type": "legal_entity"},
        headers=org_setup["headers"],
    )

    resp = await client.post(
        "/api/ownership-links",
        json={"parent_entity_id": owner2.json()["id"], "child_entity_id": child_id, "ownership_percent": 50},
        headers=org_setup["headers"],
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "OWNERSHIP_EXCEEDS_100"


# --- Control ---
@pytest.mark.asyncio
async def test_create_control_link(client: AsyncClient, org_setup: dict):
    child = await client.post(
        "/api/entities",
        json={"name": "Plant A", "entity_type": "facility"},
        headers=org_setup["headers"],
    )

    resp = await client.post(
        "/api/control-links",
        json={
            "controlling_entity_id": org_setup["root_id"],
            "controlled_entity_id": child.json()["id"],
            "control_type": "operational_control",
            "is_controlled": True,
        },
        headers=org_setup["headers"],
    )
    assert resp.status_code == 201
    assert resp.json()["control_type"] == "operational_control"


@pytest.mark.asyncio
async def test_self_control_rejected(client: AsyncClient, org_setup: dict):
    resp = await client.post(
        "/api/control-links",
        json={
            "controlling_entity_id": org_setup["root_id"],
            "controlled_entity_id": org_setup["root_id"],
            "control_type": "financial_control",
        },
        headers=org_setup["headers"],
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "SELF_CONTROL_NOT_ALLOWED"
