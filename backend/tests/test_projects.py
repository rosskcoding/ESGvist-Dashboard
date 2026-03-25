import pytest
from httpx import AsyncClient

from app.core.exceptions import AppError
from app.repositories.project_repo import ProjectRepository
from tests.conftest import TestSessionLocal


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
    return {
        "headers": headers,
        "org_id": org_id,
        "root_entity_id": org.json()["root_entity_id"],
        "default_boundary_id": org.json()["boundary_id"],
    }


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
async def test_create_project_inherits_org_defaults(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={"email": "defaults-project@test.com", "password": "password123", "full_name": "Defaults Project"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": "defaults-project@test.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    for payload in (
        {"code": "GRI", "name": "GRI"},
        {"code": "IFRS_S2", "name": "IFRS S2"},
    ):
        standard = await client.post("/api/standards", json=payload, headers=headers)
        assert standard.status_code == 201

    org = await client.post(
        "/api/organizations/setup",
        json={
            "name": "Defaults Project Org",
            "country": "DE",
            "reporting_year": 2028,
            "standards": ["GRI", "IFRS_S2"],
        },
        headers=headers,
    )
    assert org.status_code == 201
    headers["X-Organization-Id"] = str(org.json()["organization_id"])

    project = await client.post(
        "/api/projects",
        json={"name": "Inherited Defaults Project"},
        headers=headers,
    )
    assert project.status_code == 201
    assert project.json()["reporting_year"] == 2028
    assert project.json()["boundary_definition_id"] == org.json()["boundary_id"]
    assert project.json()["standard_codes"] == ["GRI", "IFRS_S2"]


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
async def test_project_repo_rejects_non_editable_fields(client: AsyncClient, org_ctx: dict):
    project = await client.post(
        "/api/projects",
        json={"name": "Repo Guard"},
        headers=org_ctx["headers"],
    )
    assert project.status_code == 201

    async with TestSessionLocal() as session:
        repo = ProjectRepository(session)
        with pytest.raises(AppError) as exc_info:
            await repo.update_project(project.json()["id"], organization_id=org_ctx["org_id"] + 1)

    assert exc_info.value.code == "PROJECT_FIELD_NOT_EDITABLE"


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

    boundaries = await client.get("/api/boundaries", headers=org_ctx["headers"])
    assert boundaries.status_code == 200
    defaults = [item for item in boundaries.json() if item["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["id"] == resp.json()["id"]


@pytest.mark.asyncio
async def test_update_boundary_promotes_single_default(client: AsyncClient, org_ctx: dict):
    boundary = await client.post(
        "/api/boundaries",
        json={"name": "Operational Boundary", "boundary_type": "operational_control"},
        headers=org_ctx["headers"],
    )
    assert boundary.status_code == 201

    promoted = await client.patch(
        f"/api/boundaries/{boundary.json()['id']}",
        json={"is_default": True},
        headers=org_ctx["headers"],
    )
    assert promoted.status_code == 200
    assert promoted.json()["is_default"] is True

    boundaries = await client.get("/api/boundaries", headers=org_ctx["headers"])
    assert boundaries.status_code == 200
    defaults = [item for item in boundaries.json() if item["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["id"] == boundary.json()["id"]


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


@pytest.mark.asyncio
async def test_apply_boundary_invalidates_existing_snapshot(client: AsyncClient, org_ctx: dict):
    boundary_a = await client.post(
        "/api/boundaries",
        json={"name": "Boundary A", "boundary_type": "financial_control"},
        headers=org_ctx["headers"],
    )
    boundary_b = await client.post(
        "/api/boundaries",
        json={"name": "Boundary B", "boundary_type": "operational_control"},
        headers=org_ctx["headers"],
    )
    project = await client.post(
        "/api/projects",
        json={"name": "Snapshot Project"},
        headers=org_ctx["headers"],
    )

    apply_a = await client.put(
        f"/api/projects/{project.json()['id']}/boundary?boundary_id={boundary_a.json()['id']}",
        headers=org_ctx["headers"],
    )
    assert apply_a.status_code == 200

    snapshot = await client.post(
        f"/api/projects/{project.json()['id']}/boundary/snapshot",
        headers=org_ctx["headers"],
    )
    assert snapshot.status_code == 200

    apply_b = await client.put(
        f"/api/projects/{project.json()['id']}/boundary?boundary_id={boundary_b.json()['id']}",
        headers=org_ctx["headers"],
    )
    assert apply_b.status_code == 200

    snapshot_after_change = await client.get(
        f"/api/projects/{project.json()['id']}/boundary/snapshot",
        headers=org_ctx["headers"],
    )
    assert snapshot_after_change.status_code == 404


@pytest.mark.asyncio
async def test_create_assignment_rejects_entity_outside_active_boundary(client: AsyncClient, org_ctx: dict):
    from app.db.models.boundary import BoundaryMembership

    boundary = await client.post(
        "/api/boundaries",
        json={"name": "Operational", "boundary_type": "operational_control"},
        headers=org_ctx["headers"],
    )
    entity_in = await client.post(
        "/api/entities",
        json={"name": "Entity In", "entity_type": "legal_entity", "parent_entity_id": org_ctx["root_entity_id"]},
        headers=org_ctx["headers"],
    )
    entity_out = await client.post(
        "/api/entities",
        json={"name": "Entity Out", "entity_type": "legal_entity", "parent_entity_id": org_ctx["root_entity_id"]},
        headers=org_ctx["headers"],
    )
    project = await client.post(
        "/api/projects",
        json={"name": "Boundary Guard Project"},
        headers=org_ctx["headers"],
    )
    shared_element = await client.post(
        "/api/shared-elements",
        json={"code": "BG1", "name": "Boundary Guard Metric"},
        headers=org_ctx["headers"],
    )
    assert boundary.status_code == 201
    assert entity_in.status_code == 201
    assert entity_out.status_code == 201
    assert project.status_code == 201

    async with TestSessionLocal() as session:
        session.add(
            BoundaryMembership(
                boundary_definition_id=boundary.json()["id"],
                entity_id=entity_in.json()["id"],
                included=True,
                inclusion_source="manual",
                consolidation_method="full",
            )
        )
        await session.commit()

    applied = await client.put(
        f"/api/projects/{project.json()['id']}/boundary",
        params={"boundary_id": boundary.json()["id"]},
        headers=org_ctx["headers"],
    )
    assert applied.status_code == 200

    resp = await client.post(
        f"/api/projects/{project.json()['id']}/assignments",
        json={
            "shared_element_id": shared_element.json()["id"],
            "entity_id": entity_out.json()["id"],
        },
        headers=org_ctx["headers"],
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "ASSIGNMENT_ENTITY_MISMATCH"


@pytest.mark.asyncio
async def test_boundary_assignments_preview_returns_added_and_removed_assignments(client: AsyncClient, org_ctx: dict):
    from app.db.models.boundary import BoundaryMembership

    boundary_a = await client.post(
        "/api/boundaries",
        json={"name": "Boundary A", "boundary_type": "financial_control"},
        headers=org_ctx["headers"],
    )
    boundary_b = await client.post(
        "/api/boundaries",
        json={"name": "Boundary B", "boundary_type": "operational_control"},
        headers=org_ctx["headers"],
    )
    entity_a = await client.post(
        "/api/entities",
        json={"name": "Entity A", "entity_type": "legal_entity", "parent_entity_id": org_ctx["root_entity_id"]},
        headers=org_ctx["headers"],
    )
    entity_b = await client.post(
        "/api/entities",
        json={"name": "Entity B", "entity_type": "legal_entity", "parent_entity_id": org_ctx["root_entity_id"]},
        headers=org_ctx["headers"],
    )
    project = await client.post(
        "/api/projects",
        json={"name": "Boundary Preview Project"},
        headers=org_ctx["headers"],
    )
    shared_element = await client.post(
        "/api/shared-elements",
        json={"code": "BP1", "name": "Boundary Preview Metric"},
        headers=org_ctx["headers"],
    )
    assert boundary_a.status_code == 201
    assert boundary_b.status_code == 201
    assert entity_a.status_code == 201
    assert entity_b.status_code == 201
    assert project.status_code == 201

    async with TestSessionLocal() as session:
        session.add_all(
            [
                BoundaryMembership(
                    boundary_definition_id=boundary_a.json()["id"],
                    entity_id=entity_a.json()["id"],
                    included=True,
                    inclusion_source="manual",
                    consolidation_method="full",
                ),
                BoundaryMembership(
                    boundary_definition_id=boundary_b.json()["id"],
                    entity_id=entity_b.json()["id"],
                    included=True,
                    inclusion_source="manual",
                    consolidation_method="full",
                ),
            ]
        )
        await session.commit()

    applied = await client.put(
        f"/api/projects/{project.json()['id']}/boundary",
        params={"boundary_id": boundary_a.json()["id"]},
        headers=org_ctx["headers"],
    )
    assert applied.status_code == 200

    assignment = await client.post(
        f"/api/projects/{project.json()['id']}/assignments",
        json={
            "shared_element_id": shared_element.json()["id"],
            "entity_id": entity_a.json()["id"],
        },
        headers=org_ctx["headers"],
    )
    assert assignment.status_code == 201

    preview = await client.get(
        f"/api/projects/{project.json()['id']}/boundary/assignments-preview",
        params={"boundary_id": boundary_b.json()["id"]},
        headers=org_ctx["headers"],
    )
    assert preview.status_code == 200
    data = preview.json()
    assert data["added_entity_ids"] == [entity_b.json()["id"]]
    assert data["removed_entity_ids"] == [entity_a.json()["id"]]
    assert data["assignment_changes"]["removed_count"] == 1
    assert data["assignment_changes"]["added_count"] == 1
    assert data["assignment_changes"]["added"][0]["entity_id"] == entity_b.json()["id"]
    assert data["assignment_changes"]["removed"][0]["entity_id"] == entity_a.json()["id"]
