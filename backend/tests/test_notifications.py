from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.db.models.notification import Notification
from tests.conftest import TestSessionLocal


async def _register_and_login(
    client: AsyncClient,
    *,
    email: str,
    password: str = "password123",
    full_name: str,
) -> dict:
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    login = await client.post("/api/auth/login", json={"email": email, "password": password})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me = await client.get("/api/auth/me", headers=headers)
    return {"headers": headers, "user_id": me.json()["id"]}


async def _invite_and_accept(
    client: AsyncClient,
    *,
    admin_headers: dict,
    org_id: int,
    email: str,
    role: str,
    full_name: str,
) -> dict:
    invitation = await client.post(
        "/api/invitations",
        json={"email": email, "role": role},
        headers=admin_headers,
    )
    assert invitation.status_code == 201

    user = await _register_and_login(client, email=email, full_name=full_name)
    accepted = await client.post(
        f"/api/invitations/accept/{invitation.json()['token']}",
        headers=user["headers"],
    )
    assert accepted.status_code == 200

    org_headers = {
        **user["headers"],
        "X-Organization-Id": str(org_id),
    }
    return {"headers": org_headers, "user_id": user["user_id"]}


@pytest.fixture
async def ctx(client: AsyncClient) -> dict:
    await client.post(
        "/api/auth/register",
        json={"email": "a@t.com", "password": "password123", "full_name": "A"},
    )
    login = await client.post("/api/auth/login", json={"email": "a@t.com", "password": "password123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    org = await client.post("/api/organizations/setup", json={"name": "Co"}, headers=headers)
    org_id = org.json()["organization_id"]
    org_headers = {**headers, "X-Organization-Id": str(org_id)}

    # Create notifications directly in DB
    async with TestSessionLocal() as session:
        notifications = [
            Notification(
                organization_id=org_id,
                user_id=1,
                type="test_event",
                title="Test 0",
                message="Message 0",
                severity="info",
            ),
            Notification(
                organization_id=org_id,
                user_id=1,
                type="assignment_overdue",
                title="Critical",
                message="Critical message",
                severity="critical",
                channel="both",
                email_sent=True,
                email_sent_at=datetime.now(timezone.utc),
            ),
            Notification(
                organization_id=org_id,
                user_id=1,
                type="test_event",
                title="Test 2",
                message="Message 2",
                severity="info",
            ),
        ]
        for notification in notifications:
            session.add(notification)
        await session.commit()

    return {"headers": org_headers, "org_id": org_id}


@pytest.mark.asyncio
async def test_list_notifications(client: AsyncClient, ctx: dict):
    resp = await client.get("/api/notifications", headers=ctx["headers"])
    assert resp.status_code == 200
    assert resp.json()["total"] == 3
    assert all(item["channel"] in {"in_app", "both"} for item in resp.json()["items"])


@pytest.mark.asyncio
async def test_list_notifications_supports_filters_and_delivery_fields(client: AsyncClient, ctx: dict):
    resp = await client.get(
        "/api/notifications",
        params={"severity": "critical", "type": "assignment_overdue", "is_read": False},
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    item = resp.json()["items"][0]
    assert item["type"] == "assignment_overdue"
    assert item["channel"] == "both"
    assert item["email_sent"] is True
    assert item["email_sent_at"] is not None


@pytest.mark.asyncio
async def test_unread_count(client: AsyncClient, ctx: dict):
    resp = await client.get("/api/notifications/unread-count", headers=ctx["headers"])
    assert resp.status_code == 200
    assert resp.json()["unread_count"] == 3


@pytest.mark.asyncio
async def test_mark_read(client: AsyncClient, ctx: dict):
    # Get first notification
    list_resp = await client.get("/api/notifications", headers=ctx["headers"])
    nid = list_resp.json()["items"][0]["id"]

    resp = await client.patch(f"/api/notifications/{nid}/read", headers=ctx["headers"])
    assert resp.status_code == 200

    # Unread count should decrease
    count = await client.get("/api/notifications/unread-count", headers=ctx["headers"])
    assert count.json()["unread_count"] == 2

    read_items = await client.get(
        "/api/notifications",
        params={"is_read": True},
        headers=ctx["headers"],
    )
    assert read_items.status_code == 200
    assert read_items.json()["items"][0]["read_at"] is not None


@pytest.mark.asyncio
async def test_mark_all_read(client: AsyncClient, ctx: dict):
    resp = await client.post("/api/notifications/read-all", headers=ctx["headers"])
    assert resp.status_code == 200

    count = await client.get("/api/notifications/unread-count", headers=ctx["headers"])
    assert count.json()["unread_count"] == 0


@pytest.mark.asyncio
async def test_auditor_cannot_access_notifications(client: AsyncClient, ctx: dict):
    admin_headers = ctx["headers"]
    auditor = await _invite_and_accept(
        client,
        admin_headers=admin_headers,
        org_id=ctx["org_id"],
        email="auditor@co.com",
        role="auditor",
        full_name="Auditor",
    )
    resp = await client.get("/api/notifications", headers=auditor["headers"])
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_assignment_created_event_notifies_assignees(client: AsyncClient, ctx: dict):
    admin_headers = {**ctx["headers"], "X-Organization-Id": str(ctx["org_id"])}
    collector = await _invite_and_accept(
        client,
        admin_headers=admin_headers,
        org_id=ctx["org_id"],
        email="collector@co.com",
        role="collector",
        full_name="Collector",
    )
    reviewer = await _invite_and_accept(
        client,
        admin_headers=admin_headers,
        org_id=ctx["org_id"],
        email="reviewer@co.com",
        role="reviewer",
        full_name="Reviewer",
    )

    project = await client.post("/api/projects", json={"name": "Notif Project"}, headers=admin_headers)
    shared_element = await client.post(
        "/api/shared-elements",
        json={"code": "N1", "name": "Notif Metric"},
        headers=admin_headers,
    )

    assignment = await client.post(
        f"/api/projects/{project.json()['id']}/assignments",
        json={
            "shared_element_id": shared_element.json()["id"],
            "collector_id": collector["user_id"],
            "reviewer_id": reviewer["user_id"],
        },
        headers=admin_headers,
    )
    assert assignment.status_code == 201

    collector_notifications = await client.get("/api/notifications", headers=collector["headers"])
    reviewer_notifications = await client.get("/api/notifications", headers=reviewer["headers"])

    collector_item = next(
        item for item in collector_notifications.json()["items"] if item["type"] == "assignment_created"
    )
    reviewer_item = next(
        item for item in reviewer_notifications.json()["items"] if item["type"] == "review_requested"
    )
    assert collector_item["channel"] == "both"
    assert collector_item["email_sent"] is True
    assert reviewer_item["channel"] == "both"
    assert reviewer_item["email_sent"] is True


@pytest.mark.asyncio
async def test_submit_event_notifies_reviewer(client: AsyncClient, ctx: dict):
    admin_headers = {**ctx["headers"], "X-Organization-Id": str(ctx["org_id"])}
    collector = await _invite_and_accept(
        client,
        admin_headers=admin_headers,
        org_id=ctx["org_id"],
        email="submit-collector@co.com",
        role="collector",
        full_name="Collector Submit",
    )
    reviewer = await _invite_and_accept(
        client,
        admin_headers=admin_headers,
        org_id=ctx["org_id"],
        email="submit-reviewer@co.com",
        role="reviewer",
        full_name="Reviewer Submit",
    )

    project = await client.post("/api/projects", json={"name": "Workflow Project"}, headers=admin_headers)
    shared_element = await client.post(
        "/api/shared-elements",
        json={"code": "WF1", "name": "Workflow Metric"},
        headers=admin_headers,
    )
    await client.post(
        f"/api/projects/{project.json()['id']}/assignments",
        json={
            "shared_element_id": shared_element.json()["id"],
            "collector_id": collector["user_id"],
            "reviewer_id": reviewer["user_id"],
        },
        headers=admin_headers,
    )

    data_point = await client.post(
        f"/api/projects/{project.json()['id']}/data-points",
        json={"shared_element_id": shared_element.json()["id"], "numeric_value": 42},
        headers=collector["headers"],
    )
    assert data_point.status_code == 201

    submit = await client.post(
        f"/api/data-points/{data_point.json()['id']}/submit",
        headers=collector["headers"],
    )
    assert submit.status_code == 200

    reviewer_notifications = await client.get("/api/notifications", headers=reviewer["headers"])
    reviewer_item = next(
        item for item in reviewer_notifications.json()["items"] if item["type"] == "data_point_submitted"
    )
    assert reviewer_item["channel"] == "both"
    assert reviewer_item["email_sent"] is True


@pytest.mark.asyncio
async def test_email_delivery_can_be_disabled(monkeypatch, client: AsyncClient, ctx: dict):
    monkeypatch.setattr(settings, "email_enabled", False)

    admin_headers = {**ctx["headers"], "X-Organization-Id": str(ctx["org_id"])}
    collector = await _invite_and_accept(
        client,
        admin_headers=admin_headers,
        org_id=ctx["org_id"],
        email="collector-disabled-email@co.com",
        role="collector",
        full_name="Collector Disabled Email",
    )
    reviewer = await _invite_and_accept(
        client,
        admin_headers=admin_headers,
        org_id=ctx["org_id"],
        email="reviewer-disabled-email@co.com",
        role="reviewer",
        full_name="Reviewer Disabled Email",
    )

    project = await client.post("/api/projects", json={"name": "Disabled Email Project"}, headers=admin_headers)
    shared_element = await client.post(
        "/api/shared-elements",
        json={"code": "DE1", "name": "Disabled Email Metric"},
        headers=admin_headers,
    )

    assignment = await client.post(
        f"/api/projects/{project.json()['id']}/assignments",
        json={
            "shared_element_id": shared_element.json()["id"],
            "collector_id": collector["user_id"],
            "reviewer_id": reviewer["user_id"],
        },
        headers=admin_headers,
    )
    assert assignment.status_code == 201

    reviewer_notifications = await client.get("/api/notifications", headers=reviewer["headers"])
    reviewer_item = next(
        item for item in reviewer_notifications.json()["items"] if item["type"] == "review_requested"
    )
    assert reviewer_item["channel"] == "both"
    assert reviewer_item["email_sent"] is False
    assert reviewer_item["email_sent_at"] is None


@pytest.mark.asyncio
async def test_email_provider_failure_does_not_block_notification_when_fail_silent(
    monkeypatch,
    client: AsyncClient,
    ctx: dict,
):
    monkeypatch.setattr(settings, "email_enabled", True)
    monkeypatch.setattr(settings, "email_provider", "failing")
    monkeypatch.setattr(settings, "email_fail_silently", True)

    admin_headers = {**ctx["headers"], "X-Organization-Id": str(ctx["org_id"])}
    collector = await _invite_and_accept(
        client,
        admin_headers=admin_headers,
        org_id=ctx["org_id"],
        email="collector-failing-email@co.com",
        role="collector",
        full_name="Collector Failing Email",
    )
    reviewer = await _invite_and_accept(
        client,
        admin_headers=admin_headers,
        org_id=ctx["org_id"],
        email="reviewer-failing-email@co.com",
        role="reviewer",
        full_name="Reviewer Failing Email",
    )

    project = await client.post("/api/projects", json={"name": "Failing Email Project"}, headers=admin_headers)
    shared_element = await client.post(
        "/api/shared-elements",
        json={"code": "FE1", "name": "Failing Email Metric"},
        headers=admin_headers,
    )

    assignment = await client.post(
        f"/api/projects/{project.json()['id']}/assignments",
        json={
            "shared_element_id": shared_element.json()["id"],
            "collector_id": collector["user_id"],
            "reviewer_id": reviewer["user_id"],
        },
        headers=admin_headers,
    )
    assert assignment.status_code == 201

    collector_notifications = await client.get("/api/notifications", headers=collector["headers"])
    collector_item = next(
        item for item in collector_notifications.json()["items"] if item["type"] == "assignment_created"
    )
    assert collector_item["channel"] == "both"
    assert collector_item["email_sent"] is False


@pytest.mark.asyncio
async def test_assignment_update_notifies_affected_users(client: AsyncClient, ctx: dict):
    admin_headers = {**ctx["headers"], "X-Organization-Id": str(ctx["org_id"])}
    collector = await _invite_and_accept(
        client,
        admin_headers=admin_headers,
        org_id=ctx["org_id"],
        email="update-collector@co.com",
        role="collector",
        full_name="Collector Update",
    )
    reviewer = await _invite_and_accept(
        client,
        admin_headers=admin_headers,
        org_id=ctx["org_id"],
        email="update-reviewer@co.com",
        role="reviewer",
        full_name="Reviewer Update",
    )
    backup = await _invite_and_accept(
        client,
        admin_headers=admin_headers,
        org_id=ctx["org_id"],
        email="update-backup@co.com",
        role="collector",
        full_name="Backup Update",
    )

    project = await client.post("/api/projects", json={"name": "Update Notification Project"}, headers=admin_headers)
    shared_element = await client.post(
        "/api/shared-elements",
        json={"code": "UPD1", "name": "Updated Metric"},
        headers=admin_headers,
    )

    assignment = await client.post(
        f"/api/projects/{project.json()['id']}/assignments",
        json={
            "shared_element_id": shared_element.json()["id"],
            "collector_id": collector["user_id"],
            "reviewer_id": reviewer["user_id"],
        },
        headers=admin_headers,
    )
    assert assignment.status_code == 201

    updated = await client.patch(
        f"/api/projects/{project.json()['id']}/assignments/inline-update",
        json={
            "id": assignment.json()["id"],
            "field": "backup_collector_id",
            "value": str(backup["user_id"]),
        },
        headers=admin_headers,
    )
    assert updated.status_code == 200

    backup_notifications = await client.get("/api/notifications", headers=backup["headers"])
    assert any(item["type"] == "assignment_updated" for item in backup_notifications.json()["items"])
