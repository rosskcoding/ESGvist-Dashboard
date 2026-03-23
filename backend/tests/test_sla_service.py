from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from app.db.models.project import ReportingProject
from app.services.sla_service import SLAService
from tests.conftest import TestSessionLocal


async def _setup_org_admin(client: AsyncClient) -> dict:
    await client.post(
        "/api/auth/register",
        json={"email": "admin+sla@org.com", "password": "password123", "full_name": "SLA Admin"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": "admin+sla@org.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    org = await client.post(
        "/api/organizations/setup",
        json={"name": "SLA Org", "country": "GB"},
        headers=headers,
    )
    headers["X-Organization-Id"] = str(org.json()["organization_id"])
    return {
        "headers": headers,
        "org_id": org.json()["organization_id"],
        "root_entity_id": org.json()["root_entity_id"],
    }


async def _invite_and_accept(
    client: AsyncClient,
    admin_headers: dict,
    *,
    email: str,
    role: str,
    full_name: str,
) -> dict:
    invitation = await client.post(
        "/api/auth/invitations",
        json={"email": email, "role": role},
        headers=admin_headers,
    )
    assert invitation.status_code == 201

    await client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123", "full_name": full_name},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "password123"},
    )
    headers = {
        "Authorization": f"Bearer {login.json()['access_token']}",
        "X-Organization-Id": admin_headers["X-Organization-Id"],
    }
    accept = await client.post(
        f"/api/invitations/accept/{invitation.json()['token']}",
        headers=headers,
    )
    assert accept.status_code == 200

    me = await client.get("/api/auth/me", headers=headers)
    return {"id": me.json()["id"], "headers": headers}


@pytest.mark.asyncio
async def test_sla_service_routes_notifications_by_escalation_level(client: AsyncClient):
    org = await _setup_org_admin(client)
    collector = await _invite_and_accept(
        client,
        org["headers"],
        email="collector+sla@org.com",
        role="collector",
        full_name="Collector SLA",
    )
    backup = await _invite_and_accept(
        client,
        org["headers"],
        email="backup+sla@org.com",
        role="collector",
        full_name="Backup SLA",
    )
    esg_manager = await _invite_and_accept(
        client,
        org["headers"],
        email="manager+sla@org.com",
        role="esg_manager",
        full_name="Manager SLA",
    )

    project = await client.post(
        "/api/projects",
        json={"name": "SLA Project"},
        headers=org["headers"],
    )
    assert project.status_code == 201

    scenarios = [
        ("SLA-WARN", {"collector_id": collector["id"], "deadline": str(date.today() + timedelta(days=2))}),
        ("SLA-OD", {"collector_id": collector["id"], "deadline": str(date.today() - timedelta(days=1))}),
        (
            "SLA-L1",
            {
                "collector_id": collector["id"],
                "backup_collector_id": backup["id"],
                "deadline": str(date.today() - timedelta(days=4)),
                "escalation_after_days": 3,
            },
        ),
        (
            "SLA-L2",
            {
                "collector_id": collector["id"],
                "backup_collector_id": backup["id"],
                "deadline": str(date.today() - timedelta(days=8)),
                "escalation_after_days": 3,
            },
        ),
    ]
    for code, payload in scenarios:
        created = await client.post(
            f"/api/projects/{project.json()['id']}/assignments",
            json={
                "shared_element_code": code,
                "shared_element_name": f"Metric {code}",
                **payload,
            },
            headers=org["headers"],
        )
        assert created.status_code == 201

    async with TestSessionLocal() as session:
        result = await SLAService(session).check_sla_breaches()
        await session.commit()

    assert result == {
        "checked": 4,
        "warnings": 1,
        "overdue": 1,
        "breach_level_1": 1,
        "breach_level_2": 1,
    }

    collector_notifications = await client.get("/api/notifications", headers=collector["headers"])
    backup_notifications = await client.get("/api/notifications", headers=backup["headers"])
    manager_notifications = await client.get("/api/notifications", headers=esg_manager["headers"])
    admin_notifications = await client.get("/api/notifications", headers=org["headers"])

    collector_types = {item["type"] for item in collector_notifications.json()["items"]}
    backup_types = {item["type"] for item in backup_notifications.json()["items"]}
    manager_types = {item["type"] for item in manager_notifications.json()["items"]}
    admin_types = {item["type"] for item in admin_notifications.json()["items"]}

    assert "deadline_approaching" in collector_types
    assert "assignment_overdue" in collector_types
    assert "assignment_escalated" in backup_types
    assert "sla_breach_level_1" in backup_types
    assert {"assignment_overdue", "sla_breach_level_1"}.issubset(manager_types)
    assert "sla_breach_level_2" in admin_types


@pytest.mark.asyncio
async def test_project_deadline_check_notifies_assigned_users(client: AsyncClient):
    org = await _setup_org_admin(client)
    collector = await _invite_and_accept(
        client,
        org["headers"],
        email="collector+project-deadline@org.com",
        role="collector",
        full_name="Collector Deadline",
    )
    reviewer = await _invite_and_accept(
        client,
        org["headers"],
        email="reviewer+project-deadline@org.com",
        role="reviewer",
        full_name="Reviewer Deadline",
    )

    project = await client.post(
        "/api/projects",
        json={"name": "Project Deadline", "deadline": str(date.today() + timedelta(days=3))},
        headers=org["headers"],
    )
    assert project.status_code == 201

    assignment = await client.post(
        f"/api/projects/{project.json()['id']}/assignments",
        json={
            "shared_element_code": "PD1",
            "shared_element_name": "Project Deadline Metric",
            "collector_id": collector["id"],
            "reviewer_id": reviewer["id"],
        },
        headers=org["headers"],
    )
    assert assignment.status_code == 201

    async with TestSessionLocal() as session:
        db_project = await session.get(ReportingProject, project.json()["id"])
        db_project.status = "active"
        await session.flush()
        result = await SLAService(session).check_project_deadlines()
        await session.commit()

    assert result == {"checked": 1, "notifications_sent": 1}

    collector_notifications = await client.get("/api/notifications", headers=collector["headers"])
    reviewer_notifications = await client.get("/api/notifications", headers=reviewer["headers"])
    assert any(item["type"] == "project_deadline_approaching" for item in collector_notifications.json()["items"])
    assert any(item["type"] == "project_deadline_approaching" for item in reviewer_notifications.json()["items"])
