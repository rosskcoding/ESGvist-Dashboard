from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models.audit_log import AuditLog
from app.db.models.project import ReportingProject
from tests.conftest import TestSessionLocal


async def _register_and_login(client: AsyncClient, *, email: str, full_name: str) -> dict:
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123", "full_name": full_name},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "password123"},
    )
    return {
        "token": login.json()["access_token"],
        "headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
    }


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
        "/api/auth/invitations",
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

    return {
        "id": (await client.get("/api/auth/me", headers=user["headers"])).json()["id"],
        "headers": {**user["headers"], "X-Organization-Id": str(org_id)},
    }


@pytest.fixture
async def platform_ctx(client: AsyncClient) -> dict:
    admin = await _register_and_login(client, email="platform@test.com", full_name="Platform Admin")
    org = await client.post(
        "/api/organizations/setup",
        json={"name": "Tenant A", "country": "GB"},
        headers=admin["headers"],
    )
    headers = dict(admin["headers"])
    headers["X-Organization-Id"] = str(org.json()["organization_id"])
    return {
        "platform_headers": admin["headers"],
        "tenant_headers": headers,
        "org_id": org.json()["organization_id"],
    }


@pytest.mark.asyncio
async def test_suspended_tenant_blocks_member_access_but_not_platform_support(
    client: AsyncClient,
    platform_ctx: dict,
):
    member = await _register_and_login(
        client, email="tenant-admin@test.com", full_name="Tenant Admin"
    )

    assigned = await client.post(
        f"/api/platform/tenants/{platform_ctx['org_id']}/admins",
        json={"user_id": 2},
        headers=platform_ctx["platform_headers"],
    )
    assert assigned.status_code == 200

    suspended = await client.post(
        f"/api/platform/tenants/{platform_ctx['org_id']}/suspend",
        headers=platform_ctx["platform_headers"],
    )
    assert suspended.status_code == 200

    login_again = await client.post(
        "/api/auth/login",
        json={"email": "tenant-admin@test.com", "password": "password123"},
    )
    assert login_again.status_code == 403
    assert login_again.json()["error"]["code"] == "TENANT_SUSPENDED"

    tenant_headers = {
        "Authorization": f"Bearer {member['token']}",
        "X-Organization-Id": str(platform_ctx["org_id"]),
    }
    blocked = await client.get("/api/projects", headers=tenant_headers)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "TENANT_SUSPENDED"

    support_headers = dict(platform_ctx["platform_headers"])
    support_headers["X-Organization-Id"] = str(platform_ctx["org_id"])
    support_view = await client.get("/api/projects", headers=support_headers)
    assert support_view.status_code == 200


@pytest.mark.asyncio
async def test_platform_admin_nonexistent_tenant_context_returns_404(
    client: AsyncClient,
    platform_ctx: dict,
):
    resp = await client.get(
        "/api/projects",
        headers={
            **platform_ctx["platform_headers"],
            "X-Organization-Id": "999999",
        },
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_support_session_allows_platform_admin_tenant_access_without_org_header(
    client: AsyncClient,
    platform_ctx: dict,
):
    project = await client.post(
        "/api/projects",
        json={"name": "Support Tenant Project"},
        headers=platform_ctx["tenant_headers"],
    )
    assert project.status_code == 201

    started = await client.post(
        f"/api/platform/tenants/{platform_ctx['org_id']}/support-session",
        json={"reason": "Investigate tenant issue"},
        headers=platform_ctx["platform_headers"],
    )
    assert started.status_code == 200

    support_view = await client.get(
        "/api/projects",
        headers={
            **platform_ctx["platform_headers"],
            "X-Support-Session-Id": str(started.json()["session_id"]),
        },
    )
    assert support_view.status_code == 200
    assert support_view.json()["total"] == 1
    assert support_view.json()["items"][0]["id"] == project.json()["id"]


@pytest.mark.asyncio
async def test_invalid_support_session_id_is_rejected(
    client: AsyncClient,
    platform_ctx: dict,
):
    resp = await client.get(
        "/api/projects",
        headers={
            **platform_ctx["platform_headers"],
            "X-Support-Session-Id": "999999",
        },
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_support_session_org_mismatch_is_rejected(
    client: AsyncClient,
    platform_ctx: dict,
):
    second_tenant = await client.post(
        "/api/platform/tenants",
        json={"name": "Tenant B", "country": "DE"},
        headers=platform_ctx["platform_headers"],
    )
    assert second_tenant.status_code == 201

    started = await client.post(
        f"/api/platform/tenants/{platform_ctx['org_id']}/support-session",
        json={"reason": "Investigate mismatch"},
        headers=platform_ctx["platform_headers"],
    )
    assert started.status_code == 200

    resp = await client.get(
        "/api/projects",
        headers={
            **platform_ctx["platform_headers"],
            "X-Support-Session-Id": str(started.json()["session_id"]),
            "X-Organization-Id": str(second_tenant.json()["id"]),
        },
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "SUPPORT_SESSION_ORG_MISMATCH"


@pytest.mark.asyncio
async def test_platform_admin_can_end_current_support_session_via_cookie(
    client: AsyncClient,
    platform_ctx: dict,
):
    started = await client.post(
        f"/api/platform/tenants/{platform_ctx['org_id']}/support-session",
        json={"reason": "Investigate tenant issue"},
        headers=platform_ctx["platform_headers"],
    )
    assert started.status_code == 200
    assert client.cookies.get("support_session_id") == str(started.json()["session_id"])

    ended = await client.delete(
        "/api/platform/support-session/current",
        headers=platform_ctx["platform_headers"],
    )
    assert ended.status_code == 200
    assert ended.json()["session_id"] == started.json()["session_id"]
    assert client.cookies.get("support_session_id") is None


@pytest.mark.asyncio
async def test_platform_admin_can_read_current_support_session_from_cookie(
    client: AsyncClient,
    platform_ctx: dict,
):
    started = await client.post(
        f"/api/platform/tenants/{platform_ctx['org_id']}/support-session",
        json={"reason": "Check current session"},
        headers=platform_ctx["platform_headers"],
    )
    assert started.status_code == 200

    current = await client.get(
        "/api/platform/support-session/current",
        headers=platform_ctx["platform_headers"],
    )
    assert current.status_code == 200
    assert current.json()["active"] is True
    assert current.json()["session_id"] == started.json()["session_id"]
    assert current.json()["tenant_id"] == platform_ctx["org_id"]
    assert current.json()["tenant_name"] == "Tenant A"


@pytest.mark.asyncio
async def test_invalid_support_session_cookie_returns_inactive_and_clears_cookie(
    client: AsyncClient,
    platform_ctx: dict,
):
    client.cookies.set("support_session_id", "not-an-int", path="/api")
    client.cookies.set("current_organization_id", str(platform_ctx["org_id"]), path="/api")

    current = await client.get(
        "/api/platform/support-session/current",
        headers=platform_ctx["platform_headers"],
    )
    assert current.status_code == 200
    assert current.json() == {
        "active": False,
        "session_id": None,
        "tenant_id": None,
        "tenant_name": None,
        "started_at": None,
    }
    set_cookie_headers = current.headers.get_list("set-cookie")
    assert any(header.startswith("support_session_id=") for header in set_cookie_headers)
    assert any(header.startswith("current_organization_id=") for header in set_cookie_headers)


@pytest.mark.asyncio
async def test_support_session_cannot_be_used_by_other_platform_admin(
    client: AsyncClient,
    platform_ctx: dict,
):
    second_admin = await _register_and_login(
        client,
        email="platform-two@test.com",
        full_name="Platform Two",
    )
    second_admin_me = await client.get("/api/auth/me", headers=second_admin["headers"])
    assert second_admin_me.status_code == 200

    grant = await client.post(
        f"/api/users/{second_admin_me.json()['id']}/roles",
        json={"role": "platform_admin", "scope_type": "platform", "scope_id": None},
        headers=platform_ctx["platform_headers"],
    )
    assert grant.status_code == 201

    started = await client.post(
        f"/api/platform/tenants/{platform_ctx['org_id']}/support-session",
        json={"reason": "Investigate tenant issue"},
        headers=platform_ctx["platform_headers"],
    )
    assert started.status_code == 200

    foreign_use = await client.get(
        "/api/projects",
        headers={
            **second_admin["headers"],
            "X-Support-Session-Id": str(started.json()["session_id"]),
        },
    )
    assert foreign_use.status_code == 404
    assert foreign_use.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_support_session_audit_logs_include_start_and_end_actions(
    client: AsyncClient,
    platform_ctx: dict,
):
    started = await client.post(
        f"/api/platform/tenants/{platform_ctx['org_id']}/support-session",
        json={"reason": "Audit support session lifecycle"},
        headers=platform_ctx["platform_headers"],
    )
    assert started.status_code == 200

    ended = await client.delete(
        "/api/platform/support-session/current",
        headers=platform_ctx["platform_headers"],
    )
    assert ended.status_code == 200

    async with TestSessionLocal() as session:
        logs = (await session.execute(select(AuditLog).order_by(AuditLog.id))).scalars().all()

    started_log = next(
        (
            log
            for log in logs
            if log.action == "support_session_started"
            and log.entity_id == started.json()["session_id"]
        ),
        None,
    )
    ended_log = next(
        (
            log
            for log in logs
            if log.action == "support_session_ended"
            and log.entity_id == started.json()["session_id"]
        ),
        None,
    )

    assert started_log is not None
    assert started_log.organization_id == platform_ctx["org_id"]
    assert started_log.performed_by_platform_admin is True
    assert started_log.changes == {
        "reason": "Audit support session lifecycle",
        "tenant_id": platform_ctx["org_id"],
    }

    assert ended_log is not None
    assert ended_log.organization_id == platform_ctx["org_id"]
    assert ended_log.performed_by_platform_admin is True


@pytest.mark.asyncio
async def test_support_session_enforces_tenant_isolation_for_tenant_and_platform_routes(
    client: AsyncClient,
    platform_ctx: dict,
):
    second_tenant = await client.post(
        "/api/platform/tenants",
        json={"name": "Tenant Isolation B", "country": "DE"},
        headers=platform_ctx["platform_headers"],
    )
    assert second_tenant.status_code == 201

    tenant_a_project = await client.post(
        "/api/projects",
        json={"name": "Support Visible Project"},
        headers=platform_ctx["tenant_headers"],
    )
    assert tenant_a_project.status_code == 201

    tenant_b_project = await client.post(
        "/api/projects",
        json={"name": "Hidden Support Project"},
        headers={
            **platform_ctx["platform_headers"],
            "X-Organization-Id": str(second_tenant.json()["id"]),
        },
    )
    assert tenant_b_project.status_code == 201

    started = await client.post(
        f"/api/platform/tenants/{platform_ctx['org_id']}/support-session",
        json={"reason": "Verify tenant isolation"},
        headers=platform_ctx["platform_headers"],
    )
    assert started.status_code == 200

    tenant_projects = await client.get(
        "/api/projects",
        headers={
            **platform_ctx["platform_headers"],
            "X-Support-Session-Id": str(started.json()["session_id"]),
        },
    )
    assert tenant_projects.status_code == 200
    assert tenant_projects.json()["total"] == 1
    assert tenant_projects.json()["items"][0]["id"] == tenant_a_project.json()["id"]

    visible_tenant_users = await client.get(
        f"/api/platform/tenants/{platform_ctx['org_id']}/users",
        headers={
            **platform_ctx["platform_headers"],
            "X-Support-Session-Id": str(started.json()["session_id"]),
        },
    )
    assert visible_tenant_users.status_code == 200
    assert visible_tenant_users.json()["total"] >= 1

    blocked_other_tenant = await client.get(
        f"/api/platform/tenants/{second_tenant.json()['id']}/users",
        headers={
            **platform_ctx["platform_headers"],
            "X-Support-Session-Id": str(started.json()["session_id"]),
        },
    )
    assert blocked_other_tenant.status_code == 409
    assert blocked_other_tenant.json()["error"]["code"] == "SUPPORT_SESSION_ORG_MISMATCH"


@pytest.mark.asyncio
async def test_last_admin_cannot_be_demoted_deactivated_or_removed(
    client: AsyncClient,
    platform_ctx: dict,
):
    await _register_and_login(client, email="sole-admin@test.com", full_name="Sole Admin")
    tenant = await client.post(
        "/api/platform/tenants",
        json={"name": "Isolated Tenant", "country": "GB"},
        headers=platform_ctx["platform_headers"],
    )
    assert tenant.status_code == 201
    tenant_id = tenant.json()["id"]

    assign_admin = await client.post(
        f"/api/platform/tenants/{tenant_id}/admins",
        json={"user_id": 2},
        headers=platform_ctx["platform_headers"],
    )
    assert assign_admin.status_code == 200

    support_headers = dict(platform_ctx["platform_headers"])
    support_headers["X-Organization-Id"] = str(tenant_id)

    demote = await client.patch(
        "/api/auth/users/2/role",
        json={"role": "esg_manager"},
        headers=support_headers,
    )
    assert demote.status_code == 422
    assert demote.json()["error"]["code"] == "LAST_ADMIN_CANNOT_LEAVE"

    deactivate = await client.patch(
        "/api/auth/users/2/status",
        json={"status": "inactive"},
        headers=support_headers,
    )
    assert deactivate.status_code == 422
    assert deactivate.json()["error"]["code"] == "LAST_ADMIN_CANNOT_LEAVE"

    remove = await client.delete(
        "/api/auth/users/2",
        headers=support_headers,
    )
    assert remove.status_code == 422
    assert remove.json()["error"]["code"] == "LAST_ADMIN_CANNOT_LEAVE"

    roles = await client.get("/api/users/2/roles", headers=platform_ctx["platform_headers"])
    binding_id = roles.json()["items"][0]["id"]
    delete_binding = await client.delete(
        f"/api/users/2/roles/{binding_id}",
        headers=platform_ctx["platform_headers"],
    )
    assert delete_binding.status_code == 422
    assert delete_binding.json()["error"]["code"] == "LAST_ADMIN_CANNOT_LEAVE"


@pytest.mark.asyncio
async def test_user_role_endpoints_support_platform_and_tenant_admin_flows(
    client: AsyncClient,
    platform_ctx: dict,
):
    tenant_admin = await _register_and_login(
        client, email="tenant-role-admin@test.com", full_name="Tenant Role Admin"
    )
    await _register_and_login(client, email="target-role@test.com", full_name="Target User")

    assign_admin = await client.post(
        f"/api/platform/tenants/{platform_ctx['org_id']}/admins",
        json={"user_id": 2},
        headers=platform_ctx["platform_headers"],
    )
    assert assign_admin.status_code == 200

    platform_create = await client.post(
        "/api/users/3/roles",
        json={
            "role": "collector",
            "scope_type": "organization",
            "scope_id": platform_ctx["org_id"],
        },
        headers=platform_ctx["platform_headers"],
    )
    assert platform_create.status_code == 201
    assert platform_create.json()["role"] == "collector"

    tenant_headers = {
        "Authorization": f"Bearer {tenant_admin['token']}",
        "X-Organization-Id": str(platform_ctx["org_id"]),
    }
    tenant_view = await client.get("/api/users/3/roles", headers=tenant_headers)
    assert tenant_view.status_code == 200
    assert tenant_view.json()["items"][0]["scope_id"] == platform_ctx["org_id"]

    forbidden = await client.post(
        "/api/users/3/roles",
        json={"role": "platform_admin", "scope_type": "platform", "scope_id": None},
        headers=tenant_headers,
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "CANNOT_ASSIGN_PLATFORM_ROLE"


@pytest.mark.asyncio
async def test_platform_actions_are_marked_in_audit_log(
    client: AsyncClient,
    platform_ctx: dict,
):
    suspended = await client.post(
        f"/api/platform/tenants/{platform_ctx['org_id']}/suspend",
        headers=platform_ctx["platform_headers"],
    )
    assert suspended.status_code == 200

    async with TestSessionLocal() as session:
        logs = (await session.execute(select(AuditLog).order_by(AuditLog.id))).scalars().all()
    assert any(
        log.action == "platform_tenant_suspended" and log.performed_by_platform_admin
        for log in logs
    )


@pytest.mark.asyncio
async def test_platform_can_trigger_sla_check_job(client: AsyncClient, platform_ctx: dict):
    collector = await _invite_and_accept(
        client,
        admin_headers=platform_ctx["tenant_headers"],
        org_id=platform_ctx["org_id"],
        email="collector+platform-job@test.com",
        role="collector",
        full_name="Collector Job",
    )

    project = await client.post(
        "/api/projects",
        json={"name": "Platform SLA Project"},
        headers=platform_ctx["tenant_headers"],
    )
    assert project.status_code == 201

    assignment = await client.post(
        f"/api/projects/{project.json()['id']}/assignments",
        json={
            "shared_element_code": "PLAT-SLA",
            "shared_element_name": "Platform SLA Metric",
            "collector_id": collector["id"],
            "deadline": str(date.today() - timedelta(days=1)),
        },
        headers=platform_ctx["tenant_headers"],
    )
    assert assignment.status_code == 201

    run = await client.post(
        "/api/platform/jobs/sla-check", headers=platform_ctx["platform_headers"]
    )
    assert run.status_code == 200
    assert run.json()["overdue"] == 1

    notifications = await client.get("/api/notifications", headers=collector["headers"])
    assert notifications.status_code == 200
    overdue = next(
        item for item in notifications.json()["items"] if item["type"] == "assignment_overdue"
    )
    assert overdue["channel"] == "both"
    assert overdue["email_sent"] is True

    async with TestSessionLocal() as session:
        logs = (await session.execute(select(AuditLog).order_by(AuditLog.id))).scalars().all()
    assert any(
        log.action == "platform_sla_check_triggered" and log.performed_by_platform_admin
        for log in logs
    )


@pytest.mark.asyncio
async def test_platform_can_trigger_project_deadline_job(client: AsyncClient, platform_ctx: dict):
    collector = await _invite_and_accept(
        client,
        admin_headers=platform_ctx["tenant_headers"],
        org_id=platform_ctx["org_id"],
        email="collector+deadline-job@test.com",
        role="collector",
        full_name="Collector Deadline Job",
    )
    reviewer = await _invite_and_accept(
        client,
        admin_headers=platform_ctx["tenant_headers"],
        org_id=platform_ctx["org_id"],
        email="reviewer+deadline-job@test.com",
        role="reviewer",
        full_name="Reviewer Deadline Job",
    )

    project = await client.post(
        "/api/projects",
        json={
            "name": "Platform Deadline Project",
            "deadline": str(date.today() + timedelta(days=3)),
        },
        headers=platform_ctx["tenant_headers"],
    )
    assert project.status_code == 201

    assignment = await client.post(
        f"/api/projects/{project.json()['id']}/assignments",
        json={
            "shared_element_code": "PLAT-DEADLINE",
            "shared_element_name": "Platform Deadline Metric",
            "collector_id": collector["id"],
            "reviewer_id": reviewer["id"],
        },
        headers=platform_ctx["tenant_headers"],
    )
    assert assignment.status_code == 201

    async with TestSessionLocal() as session:
        db_project = await session.get(ReportingProject, project.json()["id"])
        db_project.status = "active"
        await session.commit()

    run = await client.post(
        "/api/platform/jobs/project-deadlines", headers=platform_ctx["platform_headers"]
    )
    assert run.status_code == 200
    assert run.json()["notifications_sent"] == 1

    collector_notifications = await client.get("/api/notifications", headers=collector["headers"])
    reviewer_notifications = await client.get("/api/notifications", headers=reviewer["headers"])
    collector_item = next(
        item
        for item in collector_notifications.json()["items"]
        if item["type"] == "project_deadline_approaching"
    )
    reviewer_item = next(
        item
        for item in reviewer_notifications.json()["items"]
        if item["type"] == "project_deadline_approaching"
    )
    assert collector_item["email_sent"] is True
    assert reviewer_item["email_sent"] is True

    async with TestSessionLocal() as session:
        logs = (await session.execute(select(AuditLog).order_by(AuditLog.id))).scalars().all()
    assert any(
        log.action == "platform_project_deadline_check_triggered"
        and log.performed_by_platform_admin
        for log in logs
    )


@pytest.mark.asyncio
async def test_platform_can_view_job_status(client: AsyncClient, platform_ctx: dict):
    status = await client.get("/api/platform/jobs/status", headers=platform_ctx["platform_headers"])
    assert status.status_code == 200
    payload = status.json()
    assert "exports" in payload["queues"]
    assert "webhooks" in payload["queues"]
    assert "statuses" in payload["queues"]["exports"]
    assert "queue_depth" in payload["queues"]["exports"]
    assert payload["worker"]["lease_name"] == "primary"
