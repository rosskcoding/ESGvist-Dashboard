import pytest
from httpx import AsyncClient


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

    # Data point (draft)
    dp = await client.post(
        f"/api/projects/{proj.json()['id']}/data-points",
        json={"shared_element_id": el.json()["id"], "numeric_value": 1240},
        headers=headers,
    )

    return {
        "headers": headers,
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
        f"/api/projects/{ctx['project_id']}/completeness/items/{ctx['item1_id']}"
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "missing"


@pytest.mark.asyncio
async def test_bind_data_point(client: AsyncClient, ctx: dict):
    resp = await client.post(
        f"/api/projects/{ctx['project_id']}/bindings",
        json={"requirement_item_id": ctx["item1_id"], "data_point_id": ctx["dp_id"]},
    )
    assert resp.status_code == 201
    assert "binding_id" in resp.json()


@pytest.mark.asyncio
async def test_item_status_partial_not_approved(client: AsyncClient, ctx: dict):
    """Binding exists but data point is draft → partial."""
    await client.post(
        f"/api/projects/{ctx['project_id']}/bindings",
        json={"requirement_item_id": ctx["item1_id"], "data_point_id": ctx["dp_id"]},
    )

    resp = await client.get(
        f"/api/projects/{ctx['project_id']}/completeness/items/{ctx['item1_id']}"
    )
    assert resp.json()["status"] == "partial"


@pytest.mark.asyncio
async def test_item_status_complete_after_approve(client: AsyncClient, ctx: dict):
    """Binding + approved data point → complete."""
    await client.post(
        f"/api/projects/{ctx['project_id']}/bindings",
        json={"requirement_item_id": ctx["item1_id"], "data_point_id": ctx["dp_id"]},
    )

    # Set data point to approved
    from tests.conftest import TestSessionLocal
    from app.db.models.data_point import DataPoint
    from sqlalchemy import update

    async with TestSessionLocal() as session:
        await session.execute(
            update(DataPoint).where(DataPoint.id == ctx["dp_id"]).values(status="approved")
        )
        await session.commit()

    resp = await client.get(
        f"/api/projects/{ctx['project_id']}/completeness/items/{ctx['item1_id']}"
    )
    assert resp.json()["status"] == "complete"


@pytest.mark.asyncio
async def test_disclosure_status_missing(client: AsyncClient, ctx: dict):
    """No items complete → missing."""
    resp = await client.get(
        f"/api/projects/{ctx['project_id']}/completeness/disclosures/{ctx['disclosure_id']}"
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
    )

    from tests.conftest import TestSessionLocal
    from app.db.models.data_point import DataPoint
    from sqlalchemy import update

    async with TestSessionLocal() as session:
        await session.execute(
            update(DataPoint).where(DataPoint.id == ctx["dp_id"]).values(status="approved")
        )
        await session.commit()

    # Calculate item1 first
    await client.get(f"/api/projects/{ctx['project_id']}/completeness/items/{ctx['item1_id']}")
    # Calculate item2 (missing)
    await client.get(f"/api/projects/{ctx['project_id']}/completeness/items/{ctx['item2_id']}")

    resp = await client.get(
        f"/api/projects/{ctx['project_id']}/completeness/disclosures/{ctx['disclosure_id']}"
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
    )
    await client.post(
        f"/api/projects/{ctx['project_id']}/bindings",
        json={"requirement_item_id": ctx["item2_id"], "data_point_id": dp2.json()["id"]},
    )

    # Approve both
    from tests.conftest import TestSessionLocal
    from app.db.models.data_point import DataPoint
    from sqlalchemy import update

    async with TestSessionLocal() as session:
        await session.execute(
            update(DataPoint).where(DataPoint.id.in_([ctx["dp_id"], dp2.json()["id"]])).values(status="approved")
        )
        await session.commit()

    # Calculate both items
    await client.get(f"/api/projects/{ctx['project_id']}/completeness/items/{ctx['item1_id']}")
    await client.get(f"/api/projects/{ctx['project_id']}/completeness/items/{ctx['item2_id']}")

    resp = await client.get(
        f"/api/projects/{ctx['project_id']}/completeness/disclosures/{ctx['disclosure_id']}"
    )
    assert resp.json()["status"] == "complete"
    assert resp.json()["completion_percent"] == 100.0
