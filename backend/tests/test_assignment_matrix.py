from datetime import date, timedelta

import pytest
from httpx import AsyncClient


async def _setup_org_admin(client: AsyncClient) -> dict:
    await client.post(
        "/api/auth/register",
        json={"email": "admin+assign@org.com", "password": "password123", "full_name": "Assignments Admin"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": "admin+assign@org.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    org = await client.post(
        "/api/organizations/setup",
        json={"name": "Assignments Org", "country": "GB"},
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
async def test_assignment_matrix_supports_frontend_contract_and_inline_updates(client: AsyncClient):
    org = await _setup_org_admin(client)
    collector = await _invite_and_accept(
        client,
        org["headers"],
        email="collector+assign@org.com",
        role="collector",
        full_name="Collector One",
    )
    reviewer = await _invite_and_accept(
        client,
        org["headers"],
        email="reviewer+assign@org.com",
        role="reviewer",
        full_name="Reviewer One",
    )
    backup_collector = await _invite_and_accept(
        client,
        org["headers"],
        email="backup+assign@org.com",
        role="collector",
        full_name="Backup Collector",
    )
    replacement_collector = await _invite_and_accept(
        client,
        org["headers"],
        email="collector2+assign@org.com",
        role="collector",
        full_name="Collector Two",
    )

    entity = await client.post(
        "/api/entities",
        json={"name": "UK Subsidiary", "entity_type": "legal_entity", "parent_entity_id": org["root_entity_id"]},
        headers=org["headers"],
    )
    assert entity.status_code == 201

    project = await client.post(
        "/api/projects",
        json={"name": "Assignments Project"},
        headers=org["headers"],
    )
    assert project.status_code == 201

    overdue_deadline = (date.today() - timedelta(days=2)).isoformat()
    created = await client.post(
        f"/api/projects/{project.json()['id']}/assignments",
        json={
            "shared_element_code": "E1-1",
            "shared_element_name": "Energy Consumption",
            "entity_id": entity.json()["id"],
            "collector_id": collector["id"],
            "reviewer_id": reviewer["id"],
            "backup_collector_id": backup_collector["id"],
            "deadline": overdue_deadline,
            "escalation_after_days": 5,
        },
        headers=org["headers"],
    )
    assert created.status_code == 201

    listed = await client.get(
        f"/api/projects/{project.json()['id']}/assignments",
        headers=org["headers"],
    )
    assert listed.status_code == 200
    data = listed.json()
    assert {key for key in data.keys()} == {"assignments", "users", "entities"}
    assert len(data["assignments"]) == 1
    row = data["assignments"][0]
    assert row["shared_element_code"] == "E1-1"
    assert row["shared_element_name"] == "Energy Consumption"
    assert row["entity_name"] == "UK Subsidiary"
    assert row["collector_name"] == "Collector One"
    assert row["reviewer_name"] == "Reviewer One"
    assert row["backup_collector_name"] == "Backup Collector"
    assert row["escalation_after_days"] == 5
    assert row["sla_status"] == "overdue"
    assert row["status"] == "overdue"
    assert any(user["email"] == "collector+assign@org.com" for user in data["users"])
    assert any(item["name"] == "UK Subsidiary" for item in data["entities"])

    updated_deadline = await client.patch(
        f"/api/projects/{project.json()['id']}/assignments/inline-update",
        json={"id": created.json()["id"], "field": "deadline", "value": "2031-01-10"},
        headers=org["headers"],
    )
    assert updated_deadline.status_code == 200
    assert updated_deadline.json()["deadline"] == "2031-01-10"
    assert updated_deadline.json()["sla_status"] == "on_track"

    updated_backup = await client.patch(
        f"/api/projects/{project.json()['id']}/assignments/inline-update",
        json={"id": created.json()["id"], "field": "backup_collector_id", "value": str(replacement_collector['id'])},
        headers=org["headers"],
    )
    assert updated_backup.status_code == 200
    assert updated_backup.json()["backup_collector_id"] == replacement_collector["id"]
    assert updated_backup.json()["backup_collector_name"] == "Collector Two"


@pytest.mark.asyncio
async def test_assignment_bulk_update_updates_multiple_rows(client: AsyncClient):
    org = await _setup_org_admin(client)
    collector = await _invite_and_accept(
        client,
        org["headers"],
        email="collector+bulk@org.com",
        role="collector",
        full_name="Collector Bulk",
    )
    reviewer = await _invite_and_accept(
        client,
        org["headers"],
        email="reviewer+bulk@org.com",
        role="reviewer",
        full_name="Reviewer Bulk",
    )

    entity = await client.post(
        "/api/entities",
        json={"name": "Bulk Entity", "entity_type": "legal_entity", "parent_entity_id": org["root_entity_id"]},
        headers=org["headers"],
    )
    assert entity.status_code == 201

    project = await client.post(
        "/api/projects",
        json={"name": "Bulk Project"},
        headers=org["headers"],
    )
    assert project.status_code == 201

    assignment_ids = []
    for code in ("W1", "W2"):
        created = await client.post(
            f"/api/projects/{project.json()['id']}/assignments",
            json={
                "shared_element_code": code,
                "shared_element_name": f"Metric {code}",
                "entity_id": entity.json()["id"],
                "collector_id": collector["id"],
                "reviewer_id": reviewer["id"],
            },
            headers=org["headers"],
        )
        assert created.status_code == 201
        assignment_ids.append(created.json()["id"])

    bulk = await client.patch(
        f"/api/projects/{project.json()['id']}/assignments/bulk-update",
        json={"ids": assignment_ids, "field": "deadline", "value": "2032-03-15"},
        headers=org["headers"],
    )
    assert bulk.status_code == 200
    assert bulk.json()["updated_count"] == 2
    assert bulk.json()["assignment_ids"] == assignment_ids

    listed = await client.get(
        f"/api/projects/{project.json()['id']}/assignments",
        headers=org["headers"],
    )
    assert listed.status_code == 200
    deadlines = {row["shared_element_code"]: row["deadline"] for row in listed.json()["assignments"]}
    assert deadlines == {"W1": "2032-03-15", "W2": "2032-03-15"}

    bulk_escalation = await client.patch(
        f"/api/projects/{project.json()['id']}/assignments/bulk-update",
        json={"ids": assignment_ids, "field": "escalation_after_days", "value": "4"},
        headers=org["headers"],
    )
    assert bulk_escalation.status_code == 200

    listed_after_escalation = await client.get(
        f"/api/projects/{project.json()['id']}/assignments",
        headers=org["headers"],
    )
    escalation_windows = {
        row["shared_element_code"]: row["escalation_after_days"]
        for row in listed_after_escalation.json()["assignments"]
    }
    assert escalation_windows == {"W1": 4, "W2": 4}


@pytest.mark.asyncio
async def test_assignment_validation_rejects_backup_role_conflicts(client: AsyncClient):
    org = await _setup_org_admin(client)
    collector = await _invite_and_accept(
        client,
        org["headers"],
        email="collector+conflict@org.com",
        role="collector",
        full_name="Collector Conflict",
    )
    reviewer = await _invite_and_accept(
        client,
        org["headers"],
        email="reviewer+conflict@org.com",
        role="reviewer",
        full_name="Reviewer Conflict",
    )
    project = await client.post(
        "/api/projects",
        json={"name": "Conflict Project"},
        headers=org["headers"],
    )
    assert project.status_code == 201

    conflict = await client.post(
        f"/api/projects/{project.json()['id']}/assignments",
        json={
            "shared_element_code": "C1",
            "shared_element_name": "Conflict Metric",
            "collector_id": collector["id"],
            "reviewer_id": reviewer["id"],
            "backup_collector_id": collector["id"],
        },
        headers=org["headers"],
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "ASSIGNMENT_ROLE_CONFLICT"
