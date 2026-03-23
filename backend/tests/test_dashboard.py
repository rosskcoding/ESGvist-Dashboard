from datetime import date, timedelta

import pytest
from httpx import AsyncClient


@pytest.fixture
async def ctx(client: AsyncClient) -> dict:
    await client.post(
        "/api/auth/register",
        json={"email": "dashboard@test.com", "password": "password123", "full_name": "Dashboard Admin"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": "dashboard@test.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    org = await client.post("/api/organizations/setup", json={"name": "DashCo"}, headers=headers)
    headers["X-Organization-Id"] = str(org.json()["organization_id"])

    standard = await client.post(
        "/api/standards",
        json={"code": "DASH-GRI", "name": "Dashboard Standard"},
        headers=headers,
    )
    disclosure = await client.post(
        f"/api/standards/{standard.json()['id']}/disclosures",
        json={
            "code": "DASH-1",
            "title": "Dashboard Disclosure",
            "requirement_type": "quantitative",
            "mandatory_level": "mandatory",
        },
        headers=headers,
    )
    item1 = await client.post(
        f"/api/disclosures/{disclosure.json()['id']}/items",
        json={"name": "Item 1", "item_type": "metric", "value_type": "number"},
        headers=headers,
    )
    item2 = await client.post(
        f"/api/disclosures/{disclosure.json()['id']}/items",
        json={"name": "Item 2", "item_type": "metric", "value_type": "number"},
        headers=headers,
    )
    shared_element = await client.post(
        "/api/shared-elements",
        json={"code": "DASH-SE", "name": "Dashboard Metric"},
        headers=headers,
    )
    overdue_shared_element = await client.post(
        "/api/shared-elements",
        json={"code": "DASH-OD", "name": "Dashboard Overdue Metric"},
        headers=headers,
    )
    project = await client.post("/api/projects", json={"name": "Dashboard Project"}, headers=headers)
    await client.post(
        f"/api/projects/{project.json()['id']}/standards",
        json={"standard_id": standard.json()["id"], "is_base_standard": True},
        headers=headers,
    )
    data_point = await client.post(
        f"/api/projects/{project.json()['id']}/data-points",
        json={"shared_element_id": shared_element.json()["id"], "numeric_value": 10},
        headers=headers,
    )
    await client.post(
        f"/api/projects/{project.json()['id']}/bindings",
        json={"requirement_item_id": item1.json()["id"], "data_point_id": data_point.json()["id"]},
        headers=headers,
    )

    from tests.conftest import TestSessionLocal
    from sqlalchemy import update
    from app.db.models.data_point import DataPoint

    async with TestSessionLocal() as session:
        await session.execute(
            update(DataPoint).where(DataPoint.id == data_point.json()["id"]).values(status="approved")
        )
        await session.commit()

    await client.get(
        f"/api/projects/{project.json()['id']}/completeness/items/{item1.json()['id']}",
        headers=headers,
    )
    await client.get(
        f"/api/projects/{project.json()['id']}/completeness/items/{item2.json()['id']}",
        headers=headers,
    )

    assignment = await client.post(
        f"/api/projects/{project.json()['id']}/assignments",
        json={
            "shared_element_id": overdue_shared_element.json()["id"],
            "deadline": str(date.today() - timedelta(days=1)),
        },
        headers=headers,
    )
    assert assignment.status_code == 201

    return {
        "headers": headers,
        "project_id": project.json()["id"],
        "standard_id": standard.json()["id"],
    }


@pytest.mark.asyncio
async def test_dashboard_progress(client: AsyncClient, ctx: dict):
    resp = await client.get(
        f"/api/dashboard/projects/{ctx['project_id']}/progress",
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall_completion_percent"] == 50.0
    assert data["item_statuses"]["complete"] == 1
    assert data["item_statuses"]["missing"] == 1
    assert data["overdue_assignments"] == 1
    assert data["sla_counts"]["overdue"] == 1
    assert data["breached_assignments"] == []
    assert data["standards_progress"][0]["standard_id"] == ctx["standard_id"]
    assert data["standards_progress"][0]["completion_percent"] == 50.0
