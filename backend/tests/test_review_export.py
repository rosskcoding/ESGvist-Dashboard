import pytest
from httpx import AsyncClient

from tests.conftest import TestSessionLocal
from app.db.models.data_point import DataPoint
from sqlalchemy import update


async def _prepare_project_lifecycle(client: AsyncClient, headers: dict, project_id: int) -> None:
    standard = await client.post(
        "/api/standards",
        json={"code": f"STD-{project_id}", "name": f"Standard {project_id}"},
        headers=headers,
    )
    assert standard.status_code == 201

    project_standard = await client.post(
        f"/api/projects/{project_id}/standards",
        json={"standard_id": standard.json()["id"]},
        headers=headers,
    )
    assert project_standard.status_code == 200

    boundary = await client.post(
        "/api/boundaries",
        json={"name": f"Boundary {project_id}", "boundary_type": "operational_control"},
        headers=headers,
    )
    assert boundary.status_code == 201

    applied = await client.put(
        f"/api/projects/{project_id}/boundary",
        params={"boundary_id": boundary.json()["id"]},
        headers=headers,
    )
    assert applied.status_code == 200

    snapshot = await client.post(
        f"/api/projects/{project_id}/boundary/snapshot",
        headers=headers,
    )
    assert snapshot.status_code == 200


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

    await _prepare_project_lifecycle(client, headers, proj_id)

    return {
        "headers": headers,
        "project_id": proj_id,
        "dp_ids": dp_ids,
        "root_entity_id": org.json()["root_entity_id"],
        "shared_element_id": el.json()["id"],
    }


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
    resp = await client.get(f"/api/projects/{ctx['project_id']}/export/readiness", headers=ctx["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert "ready" in data
    assert "completion_percent" in data
    assert "blocking_issues" in data


@pytest.mark.asyncio
async def test_publish_project(client: AsyncClient, ctx: dict):
    review = await client.post(
        "/api/review/batch-approve",
        json={"data_point_ids": ctx["dp_ids"], "comment": "Ready to publish"},
        headers=ctx["headers"],
    )
    assert review.status_code == 200

    start = await client.post(
        f"/api/projects/{ctx['project_id']}/start",
        headers=ctx["headers"],
    )
    assert start.status_code == 200
    assert start.json()["status"] == "active"

    move_to_review = await client.post(
        f"/api/projects/{ctx['project_id']}/review",
        headers=ctx["headers"],
    )
    assert move_to_review.status_code == 200
    assert move_to_review.json()["status"] == "review"

    resp = await client.post(
        f"/api/projects/{ctx['project_id']}/publish",
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "published"


@pytest.mark.asyncio
async def test_publish_already_published(client: AsyncClient, ctx: dict):
    await client.post(
        "/api/review/batch-approve",
        json={"data_point_ids": ctx["dp_ids"], "comment": "Ready to publish"},
        headers=ctx["headers"],
    )
    await client.post(f"/api/projects/{ctx['project_id']}/start", headers=ctx["headers"])
    await client.post(f"/api/projects/{ctx['project_id']}/review", headers=ctx["headers"])
    await client.post(f"/api/projects/{ctx['project_id']}/publish", headers=ctx["headers"])
    resp = await client.post(f"/api/projects/{ctx['project_id']}/publish", headers=ctx["headers"])
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_publish_requires_current_boundary_snapshot(client: AsyncClient, ctx: dict):
    new_boundary = await client.post(
        "/api/boundaries",
        json={"name": "Updated Boundary", "boundary_type": "financial_control"},
        headers=ctx["headers"],
    )
    assert new_boundary.status_code == 201

    apply_boundary = await client.put(
        f"/api/projects/{ctx['project_id']}/boundary",
        params={"boundary_id": new_boundary.json()["id"]},
        headers=ctx["headers"],
    )
    assert apply_boundary.status_code == 200

    await client.post(
        "/api/review/batch-approve",
        json={"data_point_ids": ctx["dp_ids"], "comment": "Ready to publish"},
        headers=ctx["headers"],
    )
    await client.post(f"/api/projects/{ctx['project_id']}/start", headers=ctx["headers"])
    await client.post(f"/api/projects/{ctx['project_id']}/review", headers=ctx["headers"])

    resp = await client.post(
        f"/api/projects/{ctx['project_id']}/publish",
        headers=ctx["headers"],
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "BOUNDARY_NOT_LOCKED"


@pytest.mark.asyncio
async def test_readiness_includes_boundary_validation_details(client: AsyncClient, ctx: dict):
    from app.db.models.boundary import BoundaryMembership

    entity_a = await client.post(
        "/api/entities",
        json={"name": "Plant A", "entity_type": "legal_entity", "parent_entity_id": ctx["root_entity_id"]},
        headers=ctx["headers"],
    )
    entity_b = await client.post(
        "/api/entities",
        json={"name": "Plant B", "entity_type": "legal_entity", "parent_entity_id": ctx["root_entity_id"]},
        headers=ctx["headers"],
    )
    boundary = await client.post(
        "/api/boundaries",
        json={"name": "Operational Control", "boundary_type": "operational_control"},
        headers=ctx["headers"],
    )
    assert entity_a.status_code == 201
    assert entity_b.status_code == 201
    assert boundary.status_code == 201

    async with TestSessionLocal() as session:
        session.add_all(
            [
                BoundaryMembership(
                    boundary_definition_id=boundary.json()["id"],
                    entity_id=entity_a.json()["id"],
                    included=True,
                    inclusion_source="manual",
                    consolidation_method="full",
                ),
                BoundaryMembership(
                    boundary_definition_id=boundary.json()["id"],
                    entity_id=entity_b.json()["id"],
                    included=True,
                    inclusion_source="manual",
                    consolidation_method="full",
                ),
            ]
        )
        await session.commit()

    apply_boundary = await client.put(
        f"/api/projects/{ctx['project_id']}/boundary",
        params={"boundary_id": boundary.json()["id"]},
        headers=ctx["headers"],
    )
    assert apply_boundary.status_code == 200

    snapshot = await client.post(
        f"/api/projects/{ctx['project_id']}/boundary/snapshot",
        headers=ctx["headers"],
    )
    assert snapshot.status_code == 200

    scoped_dp = await client.post(
        f"/api/projects/{ctx['project_id']}/data-points",
        json={
            "shared_element_id": ctx["shared_element_id"],
            "entity_id": entity_a.json()["id"],
            "numeric_value": 999,
        },
        headers=ctx["headers"],
    )
    assert scoped_dp.status_code == 201

    readiness = await client.get(
        f"/api/projects/{ctx['project_id']}/export/readiness",
        headers=ctx["headers"],
    )
    assert readiness.status_code == 200
    data = readiness.json()
    assert data["boundary_validation"]["selected_boundary"] == "Operational Control"
    assert data["boundary_validation"]["snapshot_locked"] is True
    assert data["boundary_validation"]["entities_in_scope"] == 2
    assert data["boundary_validation"]["manual_overrides"] == 2
    assert data["boundary_validation"]["boundary_differs_from_default"] is True
    assert data["boundary_validation"]["entities_without_data"] == ["Plant B"]
    assert any(
        issue["code"] == "BOUNDARY_ENTITIES_WITHOUT_DATA"
        for issue in data["warning_details"]
    )


# --- Audit Log ---
@pytest.mark.asyncio
async def test_audit_log(client: AsyncClient, ctx: dict):
    # Auth actions should have created audit entries
    resp = await client.get("/api/audit-log", headers=ctx["headers"])
    assert resp.status_code == 200
    assert "items" in resp.json()
