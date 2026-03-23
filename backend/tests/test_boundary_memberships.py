import pytest
from httpx import AsyncClient

from app.db.models.project import ReportingProject
from tests.conftest import TestSessionLocal


@pytest.fixture
async def org_ctx(client: AsyncClient) -> dict:
    await client.post(
        "/api/auth/register",
        json={"email": "boundary-admin@test.com", "password": "password123", "full_name": "Boundary Admin"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": "boundary-admin@test.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    org = await client.post(
        "/api/organizations/setup",
        json={"name": "BoundaryCo", "country": "GB"},
        headers=headers,
    )
    headers["X-Organization-Id"] = str(org.json()["organization_id"])
    return {
        "headers": headers,
        "org_id": org.json()["organization_id"],
        "root_entity_id": org.json()["root_entity_id"],
        "default_boundary_id": org.json()["boundary_id"],
    }


@pytest.mark.asyncio
async def test_replace_boundary_memberships_invalidates_snapshot(client: AsyncClient, org_ctx: dict):
    boundary = await client.post(
        "/api/boundaries",
        json={"name": "Manual Boundary", "boundary_type": "operational_control"},
        headers=org_ctx["headers"],
    )
    entity_a = await client.post(
        "/api/entities",
        json={"name": "Plant A", "entity_type": "legal_entity", "parent_entity_id": org_ctx["root_entity_id"]},
        headers=org_ctx["headers"],
    )
    entity_b = await client.post(
        "/api/entities",
        json={"name": "Plant B", "entity_type": "legal_entity", "parent_entity_id": org_ctx["root_entity_id"]},
        headers=org_ctx["headers"],
    )
    project = await client.post(
        "/api/projects",
        json={"name": "Boundary Snapshot Project"},
        headers=org_ctx["headers"],
    )
    assert boundary.status_code == 201
    assert entity_a.status_code == 201
    assert entity_b.status_code == 201
    assert project.status_code == 201

    apply_boundary = await client.put(
        f"/api/projects/{project.json()['id']}/boundary",
        params={"boundary_id": boundary.json()["id"]},
        headers=org_ctx["headers"],
    )
    assert apply_boundary.status_code == 200

    snapshot = await client.post(
        f"/api/projects/{project.json()['id']}/boundary/snapshot",
        headers=org_ctx["headers"],
    )
    assert snapshot.status_code == 200

    before = await client.get(
        f"/api/boundaries/{boundary.json()['id']}/memberships",
        headers=org_ctx["headers"],
    )
    assert before.status_code == 200
    assert any(item["entity_id"] == entity_a.json()["id"] and item["explicit"] is False for item in before.json()["memberships"])

    updated = await client.put(
        f"/api/boundaries/{boundary.json()['id']}/memberships",
        json={
            "memberships": [
                {
                    "entity_id": entity_a.json()["id"],
                    "included": True,
                    "inclusion_source": "manual",
                    "consolidation_method": "full",
                },
                {
                    "entity_id": entity_b.json()["id"],
                    "included": False,
                    "inclusion_source": "override",
                    "consolidation_method": "proportional",
                },
            ]
        },
        headers=org_ctx["headers"],
    )
    assert updated.status_code == 200
    memberships = {row["entity_id"]: row for row in updated.json()["memberships"]}
    assert memberships[entity_a.json()["id"]]["included"] is True
    assert memberships[entity_a.json()["id"]]["explicit"] is True
    assert memberships[entity_a.json()["id"]]["inclusion_source"] == "manual"
    assert memberships[entity_b.json()["id"]]["included"] is False
    assert memberships[entity_b.json()["id"]]["explicit"] is True
    assert memberships[entity_b.json()["id"]]["consolidation_method"] == "proportional"

    snapshot_after_change = await client.get(
        f"/api/projects/{project.json()['id']}/boundary/snapshot",
        headers=org_ctx["headers"],
    )
    assert snapshot_after_change.status_code == 404


@pytest.mark.asyncio
async def test_boundary_memberships_blocked_when_project_locked(client: AsyncClient, org_ctx: dict):
    boundary = await client.post(
        "/api/boundaries",
        json={"name": "Locked Boundary", "boundary_type": "operational_control"},
        headers=org_ctx["headers"],
    )
    entity = await client.post(
        "/api/entities",
        json={"name": "Locked Plant", "entity_type": "legal_entity", "parent_entity_id": org_ctx["root_entity_id"]},
        headers=org_ctx["headers"],
    )
    project = await client.post(
        "/api/projects",
        json={"name": "Locked Project"},
        headers=org_ctx["headers"],
    )
    assert boundary.status_code == 201
    assert entity.status_code == 201
    assert project.status_code == 201

    apply_boundary = await client.put(
        f"/api/projects/{project.json()['id']}/boundary",
        params={"boundary_id": boundary.json()["id"]},
        headers=org_ctx["headers"],
    )
    assert apply_boundary.status_code == 200

    async with TestSessionLocal() as session:
        db_project = await session.get(ReportingProject, project.json()["id"])
        db_project.status = "review"
        await session.commit()

    blocked = await client.put(
        f"/api/boundaries/{boundary.json()['id']}/memberships",
        json={
            "memberships": [
                {
                    "entity_id": entity.json()["id"],
                    "included": True,
                    "inclusion_source": "manual",
                    "consolidation_method": "full",
                }
            ]
        },
        headers=org_ctx["headers"],
    )
    assert blocked.status_code == 422
    assert blocked.json()["error"]["code"] == "BOUNDARY_LOCKED_FOR_PROJECT"


@pytest.mark.asyncio
async def test_recalculate_default_boundary_restores_root_membership(client: AsyncClient, org_ctx: dict):
    cleared = await client.put(
        f"/api/boundaries/{org_ctx['default_boundary_id']}/memberships",
        json={"memberships": []},
        headers=org_ctx["headers"],
    )
    assert cleared.status_code == 200
    cleared_root = next(
        row for row in cleared.json()["memberships"] if row["entity_id"] == org_ctx["root_entity_id"]
    )
    assert cleared_root["explicit"] is False
    assert cleared_root["included"] is False

    recalculated = await client.post(
        f"/api/boundaries/{org_ctx['default_boundary_id']}/recalculate",
        headers=org_ctx["headers"],
    )
    assert recalculated.status_code == 200
    assert recalculated.json()["recalculated"] is True

    listed = await client.get(
        f"/api/boundaries/{org_ctx['default_boundary_id']}/memberships",
        headers=org_ctx["headers"],
    )
    assert listed.status_code == 200
    root = next(row for row in listed.json()["memberships"] if row["entity_id"] == org_ctx["root_entity_id"])
    assert root["explicit"] is True
    assert root["included"] is True
    assert root["inclusion_source"] == "automatic"
    assert root["consolidation_method"] == "full"


@pytest.mark.asyncio
async def test_boundary_definition_detail_update_and_project_context(client: AsyncClient, org_ctx: dict):
    boundary = await client.post(
        "/api/boundaries",
        json={"name": "Project Boundary", "boundary_type": "operational_control"},
        headers=org_ctx["headers"],
    )
    project = await client.post(
        "/api/projects",
        json={"name": "Boundary Context Project"},
        headers=org_ctx["headers"],
    )
    assert boundary.status_code == 201
    assert project.status_code == 201

    detail = await client.get(
        f"/api/boundaries/{boundary.json()['id']}",
        headers=org_ctx["headers"],
    )
    assert detail.status_code == 200
    assert detail.json()["name"] == "Project Boundary"

    updated = await client.patch(
        f"/api/boundaries/{boundary.json()['id']}",
        json={"description": "Updated boundary description"},
        headers=org_ctx["headers"],
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "Updated boundary description"

    applied = await client.put(
        f"/api/projects/{project.json()['id']}/boundary",
        params={"boundary_id": boundary.json()["id"]},
        headers=org_ctx["headers"],
    )
    assert applied.status_code == 200

    project_boundary = await client.get(
        f"/api/projects/{project.json()['id']}/boundary",
        headers=org_ctx["headers"],
    )
    assert project_boundary.status_code == 200
    assert project_boundary.json()["boundary_id"] == boundary.json()["id"]
    assert project_boundary.json()["boundary_name"] == "Project Boundary"
    assert project_boundary.json()["snapshot_locked"] is False
