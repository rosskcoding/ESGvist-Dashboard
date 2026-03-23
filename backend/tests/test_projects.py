import pytest
from httpx import AsyncClient


@pytest.fixture
async def org_ctx(client: AsyncClient) -> dict:
    """Register admin, setup org, return headers with org context."""
    await client.post(
        "/api/auth/register",
        json={"email": "admin@test.com", "password": "password123", "full_name": "Admin"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": "admin@test.com", "password": "password123"},
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    org = await client.post(
        "/api/organizations/setup",
        json={"name": "TestCo", "country": "KZ"},
        headers=headers,
    )
    org_id = org.json()["organization_id"]
    headers["X-Organization-Id"] = str(org_id)
    return {"headers": headers, "org_id": org_id}


# --- Projects ---
@pytest.mark.asyncio
async def test_create_project(client: AsyncClient, org_ctx: dict):
    resp = await client.post(
        "/api/projects",
        json={"name": "ESG Report 2025", "reporting_year": 2025},
        headers=org_ctx["headers"],
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "ESG Report 2025"
    assert resp.json()["status"] == "draft"


@pytest.mark.asyncio
async def test_list_projects(client: AsyncClient, org_ctx: dict):
    await client.post(
        "/api/projects",
        json={"name": "P1"},
        headers=org_ctx["headers"],
    )
    await client.post(
        "/api/projects",
        json={"name": "P2"},
        headers=org_ctx["headers"],
    )

    resp = await client.get("/api/projects", headers=org_ctx["headers"])
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


@pytest.mark.asyncio
async def test_add_standard_to_project(client: AsyncClient, org_ctx: dict):
    # Create standard
    std = await client.post(
        "/api/standards",
        json={"code": "GRI", "name": "GRI"},
        headers=org_ctx["headers"],
    )
    std_id = std.json()["id"]

    # Create project
    proj = await client.post(
        "/api/projects",
        json={"name": "Report"},
        headers=org_ctx["headers"],
    )
    proj_id = proj.json()["id"]

    # Add standard
    resp = await client.post(
        f"/api/projects/{proj_id}/standards",
        json={"standard_id": std_id, "is_base_standard": True},
        headers=org_ctx["headers"],
    )
    assert resp.status_code == 200


# --- Assignments ---
@pytest.mark.asyncio
async def test_create_assignment(client: AsyncClient, org_ctx: dict):
    # Create shared element
    el = await client.post(
        "/api/shared-elements",
        json={"code": "S1", "name": "Scope 1"},
        headers=org_ctx["headers"],
    )

    # Create project
    proj = await client.post(
        "/api/projects",
        json={"name": "Report"},
        headers=org_ctx["headers"],
    )

    resp = await client.post(
        f"/api/projects/{proj.json()['id']}/assignments",
        json={"shared_element_id": el.json()["id"]},
        headers=org_ctx["headers"],
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "assigned"


@pytest.mark.asyncio
async def test_assignment_collector_reviewer_conflict(client: AsyncClient, org_ctx: dict):
    el = await client.post(
        "/api/shared-elements",
        json={"code": "S1", "name": "Scope 1"},
        headers=org_ctx["headers"],
    )
    proj = await client.post(
        "/api/projects",
        json={"name": "Report"},
        headers=org_ctx["headers"],
    )

    # Same user as collector and reviewer
    resp = await client.post(
        f"/api/projects/{proj.json()['id']}/assignments",
        json={"shared_element_id": el.json()["id"], "collector_id": 1, "reviewer_id": 1},
        headers=org_ctx["headers"],
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ASSIGNMENT_ROLE_CONFLICT"


# --- Boundaries ---
@pytest.mark.asyncio
async def test_create_boundary(client: AsyncClient, org_ctx: dict):
    resp = await client.post(
        "/api/boundaries",
        json={"name": "Financial Default", "boundary_type": "financial_reporting_default", "is_default": True},
        headers=org_ctx["headers"],
    )
    assert resp.status_code == 201
    assert resp.json()["boundary_type"] == "financial_reporting_default"
    assert resp.json()["is_default"] is True


@pytest.mark.asyncio
async def test_list_boundaries(client: AsyncClient, org_ctx: dict):
    await client.post(
        "/api/boundaries",
        json={"name": "B1", "boundary_type": "financial_reporting_default"},
        headers=org_ctx["headers"],
    )
    await client.post(
        "/api/boundaries",
        json={"name": "B2", "boundary_type": "operational_control"},
        headers=org_ctx["headers"],
    )

    resp = await client.get("/api/boundaries", headers=org_ctx["headers"])
    assert resp.status_code == 200
    assert len(resp.json()) >= 2  # includes default boundary from org setup


@pytest.mark.asyncio
async def test_apply_boundary_to_project(client: AsyncClient, org_ctx: dict):
    boundary = await client.post(
        "/api/boundaries",
        json={"name": "OpControl", "boundary_type": "operational_control"},
        headers=org_ctx["headers"],
    )
    proj = await client.post(
        "/api/projects",
        json={"name": "Report"},
        headers=org_ctx["headers"],
    )

    resp = await client.put(
        f"/api/projects/{proj.json()['id']}/boundary?boundary_id={boundary.json()['id']}",
        headers=org_ctx["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["boundary_definition_id"] == boundary.json()["id"]
