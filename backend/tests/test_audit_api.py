import pytest
from httpx import AsyncClient


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


async def _setup_org(client: AsyncClient, *, email: str, name: str) -> dict:
    user = await _register_and_login(client, email=email, full_name="Audit Admin")
    org = await client.post(
        "/api/organizations/setup",
        json={"name": name, "country": "GB"},
        headers=user["headers"],
    )
    headers = {**user["headers"], "X-Organization-Id": str(org.json()["organization_id"])}
    return {
        "platform_headers": user["headers"],
        "tenant_headers": headers,
        "org_id": org.json()["organization_id"],
    }


async def _invite_and_accept(
    client: AsyncClient,
    *,
    admin_headers: dict,
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
    tenant_headers = {
        **user["headers"],
        "X-Organization-Id": admin_headers["X-Organization-Id"],
    }
    accepted = await client.post(
        f"/api/invitations/accept/{invitation.json()['token']}",
        headers=tenant_headers,
    )
    assert accepted.status_code == 200
    return {"headers": tenant_headers}


@pytest.mark.asyncio
async def test_admin_can_filter_audit_log_and_get_total(client: AsyncClient):
    ctx = await _setup_org(client, email="audit-admin@test.com", name="Audit Admin Org")

    updated = await client.patch(
        "/api/auth/organization/auth-settings",
        json={"allow_sso_login": False},
        headers=ctx["tenant_headers"],
    )
    assert updated.status_code == 200

    logs = await client.get(
        "/api/audit-log",
        params={
            "entity_type": "Organization",
            "action": "organization_auth_settings_updated",
        },
        headers=ctx["tenant_headers"],
    )
    assert logs.status_code == 200
    payload = logs.json()
    assert payload["total"] >= 1
    assert payload["items"][0]["entity_type"] == "Organization"
    assert payload["items"][0]["action"] == "organization_auth_settings_updated"


@pytest.mark.asyncio
async def test_auditor_can_read_tenant_audit_but_collector_cannot(client: AsyncClient):
    ctx = await _setup_org(client, email="audit-roles@test.com", name="Audit Roles Org")
    auditor = await _invite_and_accept(
        client,
        admin_headers=ctx["tenant_headers"],
        email="auditor+audit@test.com",
        role="auditor",
        full_name="Audit Reader",
    )
    collector = await _invite_and_accept(
        client,
        admin_headers=ctx["tenant_headers"],
        email="collector+audit@test.com",
        role="collector",
        full_name="Audit Collector",
    )

    auditor_resp = await client.get("/api/audit-log", headers=auditor["headers"])
    assert auditor_resp.status_code == 200
    assert "total" in auditor_resp.json()

    collector_resp = await client.get("/api/audit-log", headers=collector["headers"])
    assert collector_resp.status_code == 403
    assert collector_resp.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_platform_admin_can_filter_tenant_audit_and_export_csv(client: AsyncClient):
    ctx = await _setup_org(client, email="audit-platform@test.com", name="Audit Platform Org")

    tenant = await client.post(
        "/api/platform/tenants",
        json={"name": "Support Target", "country": "GB"},
        headers=ctx["platform_headers"],
    )
    assert tenant.status_code == 201

    filtered = await client.get(
        "/api/audit-log",
        params={
            "organization_id": tenant.json()["id"],
            "action": "platform_tenant_created",
            "performed_by_platform_admin": True,
        },
        headers=ctx["platform_headers"],
    )
    assert filtered.status_code == 200
    data = filtered.json()
    assert data["total"] == 1
    assert data["items"][0]["performed_by_platform_admin"] is True
    assert data["items"][0]["organization_id"] == tenant.json()["id"]

    exported = await client.get(
        "/api/audit-log/export",
        params={
            "format": "csv",
            "organization_id": tenant.json()["id"],
            "action": "platform_tenant_created",
        },
        headers=ctx["platform_headers"],
    )
    assert exported.status_code == 200
    export_payload = exported.json()
    assert export_payload["format"] == "csv"
    assert export_payload["content_type"] == "text/csv"
    assert "platform_tenant_created" in export_payload["content"]
    assert export_payload["filename"].endswith(".csv")
