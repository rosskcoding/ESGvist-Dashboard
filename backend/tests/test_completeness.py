import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.db.models.boundary import BoundaryMembership
from app.db.models.completeness import RequirementItemDataPoint
from app.db.models.data_point import DataPoint
from tests.conftest import TestSessionLocal


@pytest.fixture
async def ctx(client: AsyncClient) -> dict:
    """Full setup: org, project, standard, disclosure, items, shared elements, data points."""
    # Register + login
    await client.post(
        "/api/auth/register",
        json={"email": "admin@test.com", "password": "password123", "full_name": "Admin"},
    )
    login = await client.post(
        "/api/auth/login", json={"email": "admin@test.com", "password": "password123"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # Org
    org = await client.post("/api/organizations/setup", json={"name": "Co"}, headers=headers)
    headers["X-Organization-Id"] = str(org.json()["organization_id"])

    # Standard + disclosure
    std = await client.post(
        "/api/standards", json={"code": "GRI", "name": "GRI"}, headers=headers
    )
    disc = await client.post(
        f"/api/standards/{std.json()['id']}/disclosures",
        json={"code": "305-1", "title": "Emissions", "requirement_type": "quantitative", "mandatory_level": "mandatory"},
        headers=headers,
    )

    # Requirement items
    item1 = await client.post(
        f"/api/disclosures/{disc.json()['id']}/items",
        json={"name": "Scope 1 total", "item_type": "metric", "value_type": "number", "is_required": True},
        headers=headers,
    )
    item2 = await client.post(
        f"/api/disclosures/{disc.json()['id']}/items",
        json={"name": "Methodology", "item_type": "narrative", "value_type": "text", "is_required": True},
        headers=headers,
    )

    # Shared element
    el = await client.post(
        "/api/shared-elements", json={"code": "S1", "name": "Scope 1"}, headers=headers
    )

    # Project
    proj = await client.post("/api/projects", json={"name": "Report"}, headers=headers)
    await client.post(
        f"/api/projects/{proj.json()['id']}/standards",
        json={"standard_id": std.json()["id"], "is_base_standard": True},
        headers=headers,
    )

    # Data point (draft)
    dp = await client.post(
        f"/api/projects/{proj.json()['id']}/data-points",
        json={"shared_element_id": el.json()["id"], "numeric_value": 1240},
        headers=headers,
    )

    return {
        "headers": headers,
        "root_entity_id": org.json()["root_entity_id"],
        "default_boundary_id": org.json()["boundary_id"],
        "standard_id": std.json()["id"],
        "project_id": proj.json()["id"],
        "disclosure_id": disc.json()["id"],
        "item1_id": item1.json()["id"],
        "item2_id": item2.json()["id"],
        "dp_id": dp.json()["id"],
        "element_id": el.json()["id"],
    }


@pytest.mark.asyncio
async def test_item_status_missing_no_binding(client: AsyncClient, ctx: dict):
    """No binding → missing."""
    resp = await client.get(
        f"/api/projects/{ctx['project_id']}/completeness/items/{ctx['item1_id']}",
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "missing"


@pytest.mark.asyncio
async def test_bind_data_point(client: AsyncClient, ctx: dict):
    resp = await client.post(
        f"/api/projects/{ctx['project_id']}/bindings",
        json={"requirement_item_id": ctx["item1_id"], "data_point_id": ctx["dp_id"]},
        headers=ctx["headers"],
    )
    assert resp.status_code == 201
    assert "binding_id" in resp.json()


@pytest.mark.asyncio
async def test_bind_data_point_is_idempotent(client: AsyncClient, ctx: dict):
    first = await client.post(
        f"/api/projects/{ctx['project_id']}/bindings",
        json={"requirement_item_id": ctx["item1_id"], "data_point_id": ctx["dp_id"]},
        headers=ctx["headers"],
    )
    second = await client.post(
        f"/api/projects/{ctx['project_id']}/bindings",
        json={"requirement_item_id": ctx["item1_id"], "data_point_id": ctx["dp_id"]},
        headers=ctx["headers"],
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["binding_id"] == first.json()["binding_id"]

    async with TestSessionLocal() as session:
        bindings = (
            await session.execute(
                select(RequirementItemDataPoint).where(
                    RequirementItemDataPoint.reporting_project_id == ctx["project_id"],
                    RequirementItemDataPoint.requirement_item_id == ctx["item1_id"],
                    RequirementItemDataPoint.data_point_id == ctx["dp_id"],
                )
            )
        ).scalars().all()

    assert len(bindings) == 1


@pytest.mark.asyncio
async def test_item_status_partial_not_approved(client: AsyncClient, ctx: dict):
    """Binding exists but data point is draft → partial."""
    await client.post(
        f"/api/projects/{ctx['project_id']}/bindings",
        json={"requirement_item_id": ctx["item1_id"], "data_point_id": ctx["dp_id"]},
        headers=ctx["headers"],
    )

    resp = await client.get(
        f"/api/projects/{ctx['project_id']}/completeness/items/{ctx['item1_id']}",
        headers=ctx["headers"],
    )
    assert resp.json()["status"] == "partial"


@pytest.mark.asyncio
async def test_item_status_complete_after_approve(client: AsyncClient, ctx: dict):
    """Binding + approved data point → complete."""
    await client.post(
        f"/api/projects/{ctx['project_id']}/bindings",
        json={"requirement_item_id": ctx["item1_id"], "data_point_id": ctx["dp_id"]},
        headers=ctx["headers"],
    )

    # Set data point to approved
    from sqlalchemy import update

    from app.db.models.data_point import DataPoint
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as session:
        await session.execute(
            update(DataPoint).where(DataPoint.id == ctx["dp_id"]).values(status="approved")
        )
        await session.commit()

    resp = await client.get(
        f"/api/projects/{ctx['project_id']}/completeness/items/{ctx['item1_id']}",
        headers=ctx["headers"],
    )
    assert resp.json()["status"] == "complete"


@pytest.mark.asyncio
async def test_disclosure_status_missing(client: AsyncClient, ctx: dict):
    """No items complete → missing."""
    resp = await client.get(
        f"/api/projects/{ctx['project_id']}/completeness/disclosures/{ctx['disclosure_id']}",
        headers=ctx["headers"],
    )
    assert resp.json()["status"] == "missing"
    assert resp.json()["completion_percent"] == 0


@pytest.mark.asyncio
async def test_disclosure_status_partial(client: AsyncClient, ctx: dict):
    """1 of 2 items complete → partial, 50%."""
    # Bind + approve item1
    await client.post(
        f"/api/projects/{ctx['project_id']}/bindings",
        json={"requirement_item_id": ctx["item1_id"], "data_point_id": ctx["dp_id"]},
        headers=ctx["headers"],
    )

    from sqlalchemy import update

    from app.db.models.data_point import DataPoint
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as session:
        await session.execute(
            update(DataPoint).where(DataPoint.id == ctx["dp_id"]).values(status="approved")
        )
        await session.commit()

    # Calculate item1 first
    await client.get(f"/api/projects/{ctx['project_id']}/completeness/items/{ctx['item1_id']}", headers=ctx["headers"])
    # Calculate item2 (missing)
    await client.get(f"/api/projects/{ctx['project_id']}/completeness/items/{ctx['item2_id']}", headers=ctx["headers"])

    resp = await client.get(
        f"/api/projects/{ctx['project_id']}/completeness/disclosures/{ctx['disclosure_id']}",
        headers=ctx["headers"],
    )
    assert resp.json()["status"] == "partial"
    assert resp.json()["completion_percent"] == 50.0


@pytest.mark.asyncio
async def test_disclosure_status_complete(client: AsyncClient, ctx: dict):
    """All items complete → complete, 100%."""
    # Create second data point for item2
    dp2 = await client.post(
        f"/api/projects/{ctx['project_id']}/data-points",
        json={"shared_element_id": ctx["element_id"], "text_value": "GHG Protocol"},
        headers=ctx["headers"],
    )

    # Bind both
    await client.post(
        f"/api/projects/{ctx['project_id']}/bindings",
        json={"requirement_item_id": ctx["item1_id"], "data_point_id": ctx["dp_id"]},
        headers=ctx["headers"],
    )
    await client.post(
        f"/api/projects/{ctx['project_id']}/bindings",
        json={"requirement_item_id": ctx["item2_id"], "data_point_id": dp2.json()["id"]},
        headers=ctx["headers"],
    )

    # Approve both
    from sqlalchemy import update

    from app.db.models.data_point import DataPoint
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as session:
        await session.execute(
            update(DataPoint).where(DataPoint.id.in_([ctx["dp_id"], dp2.json()["id"]])).values(status="approved")
        )
        await session.commit()

    # Calculate both items
    await client.get(f"/api/projects/{ctx['project_id']}/completeness/items/{ctx['item1_id']}", headers=ctx["headers"])
    await client.get(f"/api/projects/{ctx['project_id']}/completeness/items/{ctx['item2_id']}", headers=ctx["headers"])

    resp = await client.get(
        f"/api/projects/{ctx['project_id']}/completeness/disclosures/{ctx['disclosure_id']}",
        headers=ctx["headers"],
    )
    assert resp.json()["status"] == "complete"
    assert resp.json()["completion_percent"] == 100.0


@pytest.mark.asyncio
async def test_project_completeness_overall(client: AsyncClient, ctx: dict):
    await client.post(
        f"/api/projects/{ctx['project_id']}/bindings",
        json={"requirement_item_id": ctx["item1_id"], "data_point_id": ctx["dp_id"]},
        headers=ctx["headers"],
    )

    from sqlalchemy import update

    from app.db.models.data_point import DataPoint
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as session:
        await session.execute(
            update(DataPoint).where(DataPoint.id == ctx["dp_id"]).values(status="approved")
        )
        await session.commit()

    await client.get(
        f"/api/projects/{ctx['project_id']}/completeness/items/{ctx['item1_id']}",
        headers=ctx["headers"],
    )
    await client.get(
        f"/api/projects/{ctx['project_id']}/completeness/items/{ctx['item2_id']}",
        headers=ctx["headers"],
    )

    resp = await client.get(
        f"/api/projects/{ctx['project_id']}/completeness",
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall_status"] == "partial"
    assert data["overall_percent"] == 50.0
    assert len(data["items"]) == 2
    assert len(data["disclosures"]) == 1


@pytest.mark.asyncio
async def test_project_completeness_per_standard(client: AsyncClient, ctx: dict):
    await client.post(
        f"/api/projects/{ctx['project_id']}/bindings",
        json={"requirement_item_id": ctx["item1_id"], "data_point_id": ctx["dp_id"]},
        headers=ctx["headers"],
    )

    from sqlalchemy import update

    from app.db.models.data_point import DataPoint
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as session:
        await session.execute(
            update(DataPoint).where(DataPoint.id == ctx["dp_id"]).values(status="approved")
        )
        await session.commit()

    await client.get(
        f"/api/projects/{ctx['project_id']}/completeness/items/{ctx['item1_id']}",
        headers=ctx["headers"],
    )
    await client.get(
        f"/api/projects/{ctx['project_id']}/completeness/items/{ctx['item2_id']}",
        headers=ctx["headers"],
    )

    resp = await client.get(
        f"/api/projects/{ctx['project_id']}/completeness/{ctx['standard_id']}",
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["standard_id"] == ctx["standard_id"]
    assert data["overall_percent"] == 50.0


@pytest.mark.asyncio
async def test_project_completeness_with_boundary_context(client: AsyncClient, ctx: dict):
    from sqlalchemy import update

    from app.db.models.boundary import BoundaryMembership
    from app.db.models.data_point import DataPoint
    from tests.conftest import TestSessionLocal

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
    entity_c = await client.post(
        "/api/entities",
        json={"name": "Plant C", "entity_type": "legal_entity", "parent_entity_id": ctx["root_entity_id"]},
        headers=ctx["headers"],
    )
    boundary = await client.post(
        "/api/boundaries",
        json={"name": "Operational Control", "boundary_type": "operational_control"},
        headers=ctx["headers"],
    )
    assert entity_a.status_code == 201
    assert entity_b.status_code == 201
    assert entity_c.status_code == 201
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

    applied = await client.put(
        f"/api/projects/{ctx['project_id']}/boundary",
        params={"boundary_id": boundary.json()["id"]},
        headers=ctx["headers"],
    )
    assert applied.status_code == 200

    snapshot = await client.post(
        f"/api/projects/{ctx['project_id']}/boundary/snapshot",
        headers=ctx["headers"],
    )
    assert snapshot.status_code == 200

    scoped_dp = await client.post(
        f"/api/projects/{ctx['project_id']}/data-points",
        json={
            "shared_element_id": ctx["element_id"],
            "entity_id": entity_a.json()["id"],
            "numeric_value": 321,
        },
        headers=ctx["headers"],
    )
    assert scoped_dp.status_code == 201

    await client.post(
        f"/api/projects/{ctx['project_id']}/bindings",
        json={"requirement_item_id": ctx["item1_id"], "data_point_id": scoped_dp.json()["id"]},
        headers=ctx["headers"],
    )

    async with TestSessionLocal() as session:
        await session.execute(
            update(DataPoint).where(DataPoint.id == scoped_dp.json()["id"]).values(status="approved")
        )
        await session.commit()

    item_status = await client.get(
        f"/api/projects/{ctx['project_id']}/completeness/items/{ctx['item1_id']}",
        headers=ctx["headers"],
    )
    assert item_status.status_code == 200
    assert item_status.json()["status"] == "complete"

    await client.get(
        f"/api/projects/{ctx['project_id']}/completeness/items/{ctx['item2_id']}",
        headers=ctx["headers"],
    )
    await client.get(
        f"/api/projects/{ctx['project_id']}/completeness/disclosures/{ctx['disclosure_id']}",
        headers=ctx["headers"],
    )

    resp = await client.get(
        f"/api/projects/{ctx['project_id']}/completeness?boundaryContext=true",
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["boundary_context"]["boundary_name"] == "Operational Control"
    assert data["boundary_context"]["entities_in_scope"] == 2
    assert data["boundary_context"]["snapshot_locked"] is True
    assert data["boundary_context"]["entities_without_data"] == ["Plant B"]
    assert data["overall_status"] == "partial"
    assert data["disclosures"][0]["entity_breakdown"] == {
        "covered_entities": 1,
        "missing_entities": 1,
        "excluded_entities": 1,
        "missing_entity_names": ["Plant B"],
    }


@pytest.mark.asyncio
async def test_boundary_coverage_rule_blocks_item_without_full_boundary_coverage(client: AsyncClient, ctx: dict):
    entity_a = await client.post(
        "/api/entities",
        json={"name": "Ops A", "entity_type": "legal_entity", "parent_entity_id": ctx["root_entity_id"]},
        headers=ctx["headers"],
    )
    entity_b = await client.post(
        "/api/entities",
        json={"name": "Ops B", "entity_type": "legal_entity", "parent_entity_id": ctx["root_entity_id"]},
        headers=ctx["headers"],
    )
    boundary = await client.post(
        "/api/boundaries",
        json={"name": "Boundary Coverage", "boundary_type": "operational_control"},
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

    scoped_item = await client.post(
        f"/api/disclosures/{ctx['disclosure_id']}/items",
        json={
            "item_code": "BOUNDARY-COVERAGE",
            "name": "Boundary Coverage Metric",
            "item_type": "metric",
            "value_type": "number",
            "unit_code": "MWH",
            "is_required": True,
            "granularity_rule": {"boundary_coverage_required": True},
            "sort_order": 30,
        },
        headers=ctx["headers"],
    )
    assert scoped_item.status_code == 201

    applied = await client.put(
        f"/api/projects/{ctx['project_id']}/boundary",
        params={"boundary_id": boundary.json()["id"]},
        headers=ctx["headers"],
    )
    assert applied.status_code == 200

    snapshot = await client.post(
        f"/api/projects/{ctx['project_id']}/boundary/snapshot",
        headers=ctx["headers"],
    )
    assert snapshot.status_code == 200

    scoped_dp = await client.post(
        f"/api/projects/{ctx['project_id']}/data-points",
        json={
            "shared_element_id": ctx["element_id"],
            "entity_id": entity_a.json()["id"],
            "numeric_value": 999,
        },
        headers=ctx["headers"],
    )
    assert scoped_dp.status_code == 201

    bind = await client.post(
        f"/api/projects/{ctx['project_id']}/bindings",
        json={"requirement_item_id": scoped_item.json()["id"], "data_point_id": scoped_dp.json()["id"]},
        headers=ctx["headers"],
    )
    assert bind.status_code == 201

    async with TestSessionLocal() as session:
        await session.execute(
            update(DataPoint).where(DataPoint.id == scoped_dp.json()["id"]).values(status="approved")
        )
        await session.commit()

    item_status = await client.get(
        f"/api/projects/{ctx['project_id']}/completeness/items/{scoped_item.json()['id']}",
        headers=ctx["headers"],
    )
    assert item_status.status_code == 200
    assert item_status.json()["status"] == "partial"
