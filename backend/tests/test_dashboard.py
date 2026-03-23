from datetime import date, datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.db.models.audit_log import AuditLog
from app.db.models.data_point import DataPoint
from tests.conftest import TestSessionLocal


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
    me = await client.get("/api/auth/me", headers=headers)

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
    boundaries = await client.get("/api/boundaries", headers=headers)
    await client.put(
        f"/api/projects/{project.json()['id']}/boundary?boundary_id={boundaries.json()[0]['id']}",
        headers=headers,
    )
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
        "/api/mappings",
        json={
            "requirement_item_id": item1.json()["id"],
            "shared_element_id": shared_element.json()["id"],
        },
        headers=headers,
    )
    await client.post(
        f"/api/projects/{project.json()['id']}/bindings",
        json={"requirement_item_id": item1.json()["id"], "data_point_id": data_point.json()["id"]},
        headers=headers,
    )

    from sqlalchemy import update

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
        "org_id": org.json()["organization_id"],
        "user_id": me.json()["id"],
        "data_point_id": data_point.json()["id"],
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
    assert data["issues_count"] == 1
    assert data["overdue_assignments"] == 1
    assert data["sla_counts"]["overdue"] == 1
    assert data["breached_assignments"] == []
    assert data["standards_progress"][0]["standard_id"] == ctx["standard_id"]
    assert data["standards_progress"][0]["completion_percent"] == 50.0
    assert data["coverage_by_standard"][0]["completion_percent"] == 50.0
    assert data["coverage_by_disclosure"][0]["status"] == "missing"
    assert data["coverage_by_user"] == []
    assert data["coverage_heatmap"][0]["disclosure_code"] == "DASH-1"
    assert data["priority_tasks"][0]["sla_status"] == "overdue"
    assert data["merge_summary"]["orphans"] == 1
    assert data["merge_coverage"]["DASH-GRI"]["completion_percent"] == 50.0
    assert data["boundary_summary"] is not None
    assert data["boundary_summary"]["snapshot_status"] == "missing"
    assert data["boundary_impact"]["entities_without_assigned_owners"] == 1


@pytest.mark.asyncio
async def test_dashboard_overview_and_priority_tasks(client: AsyncClient, ctx: dict):
    overview = await client.get(
        f"/api/dashboard/projects/{ctx['project_id']}/overview",
        headers=ctx["headers"],
    )
    assert overview.status_code == 200
    assert overview.json()["project_id"] == ctx["project_id"]

    tasks = await client.get(
        f"/api/dashboard/projects/{ctx['project_id']}/priority-tasks",
        headers=ctx["headers"],
    )
    assert tasks.status_code == 200
    data = tasks.json()
    assert data["project_id"] == ctx["project_id"]
    assert len(data["items"]) == 1
    assert data["items"][0]["sla_status"] == "overdue"


@pytest.mark.asyncio
async def test_dashboard_analytics_trends_and_activity(client: AsyncClient, ctx: dict):
    now = datetime.now(timezone.utc)
    async with TestSessionLocal() as session:
        session.add_all(
            [
                AuditLog(
                    organization_id=ctx["org_id"],
                    user_id=ctx["user_id"],
                    entity_type="DataPoint",
                    entity_id=ctx["data_point_id"],
                    action="data_point_submitted",
                    created_at=now - timedelta(days=1),
                ),
                AuditLog(
                    organization_id=ctx["org_id"],
                    user_id=ctx["user_id"],
                    entity_type="ReportingProject",
                    entity_id=ctx["project_id"],
                    action="project_started",
                    created_at=now - timedelta(days=1),
                ),
            ]
        )
        await session.commit()

    trends = await client.get(
        f"/api/dashboard/projects/{ctx['project_id']}/analytics/trends?days=7",
        headers=ctx["headers"],
    )
    assert trends.status_code == 200
    trend_data = trends.json()
    assert trend_data["window"]["days"] == 7
    assert len(trend_data["series"]) == 7
    assert trend_data["totals"]["created_data_points"] == 1
    assert trend_data["totals"]["submitted_data_points"] == 1
    assert trend_data["totals"]["project_started"] == 1

    activity = await client.get(
        f"/api/dashboard/projects/{ctx['project_id']}/analytics/activity",
        headers=ctx["headers"],
    )
    assert activity.status_code == 200
    activity_data = activity.json()
    assert activity_data["project_id"] == ctx["project_id"]
    assert activity_data["sla_summary"]["total_assignments"] == 1
    assert activity_data["sla_summary"]["overdue_assignments"] == 1
    assert activity_data["sla_summary"]["completion_percent"] == 0.0
    admin_activity = next(item for item in activity_data["users"] if item["user_id"] == ctx["user_id"])
    assert admin_activity["created_data_points"] == 1
    assert admin_activity["submitted_data_points"] == 1
