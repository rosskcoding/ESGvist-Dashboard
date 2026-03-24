import pytest
from httpx import AsyncClient


async def _setup_org_admin(client: AsyncClient) -> dict:
    await client.post(
        "/api/auth/register",
        json={"email": "admin@org.com", "password": "password123", "full_name": "Org Admin"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": "admin@org.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    org = await client.post(
        "/api/organizations/setup",
        json={"name": "Org Co", "country": "GB"},
        headers=headers,
    )
    headers["X-Organization-Id"] = str(org.json()["organization_id"])
    return {"headers": headers, "org_id": org.json()["organization_id"]}


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
    user_headers = {
        "Authorization": f"Bearer {login.json()['access_token']}",
        "X-Organization-Id": admin_headers["X-Organization-Id"],
    }
    accept = await client.post(
        f"/api/invitations/accept/{invitation.json()['token']}",
        headers=user_headers,
    )
    assert accept.status_code == 200

    me = await client.get("/api/auth/me", headers=user_headers)
    return {"headers": user_headers, "user_id": me.json()["id"]}


@pytest.mark.asyncio
async def test_organization_users_response_includes_users_and_pending_invitations(
    client: AsyncClient,
):
    org = await _setup_org_admin(client)
    invited = await _invite_and_accept(
        client,
        org["headers"],
        email="reviewer@org.com",
        role="reviewer",
        full_name="Review User",
    )
    assert invited["user_id"] > 0

    pending = await client.post(
        "/api/auth/invitations",
        json={"email": "pending@org.com", "role": "collector"},
        headers=org["headers"],
    )
    assert pending.status_code == 201

    resp = await client.get("/api/auth/organization/users", headers=org["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert {key for key in data.keys()} == {"users", "pending_invitations"}
    assert any(
        user["email"] == "admin@org.com" and user["role"] == "admin"
        for user in data["users"]
    )
    assert any(
        user["email"] == "reviewer@org.com" and user["role"] == "reviewer"
        for user in data["users"]
    )
    assert any(
        inv["email"] == "pending@org.com" and inv["role"] == "collector"
        for inv in data["pending_invitations"]
    )


@pytest.mark.asyncio
async def test_manage_org_user_role_status_and_remove(client: AsyncClient):
    org = await _setup_org_admin(client)
    collector = await _invite_and_accept(
        client,
        org["headers"],
        email="collector@org.com",
        role="collector",
        full_name="Collector User",
    )

    role_resp = await client.patch(
        f"/api/auth/users/{collector['user_id']}/role",
        json={"role": "reviewer"},
        headers=org["headers"],
    )
    assert role_resp.status_code == 200
    assert role_resp.json()["role"] == "reviewer"

    status_resp = await client.patch(
        f"/api/auth/users/{collector['user_id']}/status",
        json={"status": "inactive"},
        headers=org["headers"],
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "inactive"

    blocked = await client.get("/api/auth/me", headers=collector["headers"])
    assert blocked.status_code == 401

    reactivate = await client.patch(
        f"/api/auth/users/{collector['user_id']}/status",
        json={"status": "active"},
        headers=org["headers"],
    )
    assert reactivate.status_code == 200
    assert reactivate.json()["status"] == "active"

    collector_relogin = await client.post(
        "/api/auth/login",
        json={"email": "collector@org.com", "password": "password123"},
    )
    assert collector_relogin.status_code == 200
    collector_headers = {
        "Authorization": f"Bearer {collector_relogin.json()['access_token']}",
        "X-Organization-Id": org["headers"]["X-Organization-Id"],
    }

    remove = await client.delete(
        f"/api/auth/users/{collector['user_id']}",
        headers=org["headers"],
    )
    assert remove.status_code == 200
    assert remove.json()["removed"] is True

    no_org_access = await client.get("/api/projects", headers=collector_headers)
    assert no_org_access.status_code == 403


@pytest.mark.asyncio
async def test_auth_invitation_resend_and_cancel(client: AsyncClient):
    org = await _setup_org_admin(client)

    created = await client.post(
        "/api/auth/invitations",
        json={"email": "temp@org.com", "role": "collector"},
        headers=org["headers"],
    )
    assert created.status_code == 201
    original_token = created.json()["token"]

    resent = await client.post(
        f"/api/auth/invitations/{created.json()['id']}/resend",
        headers=org["headers"],
    )
    assert resent.status_code == 200
    assert resent.json()["token"] != original_token

    cancelled = await client.delete(
        f"/api/auth/invitations/{created.json()['id']}",
        headers=org["headers"],
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["cancelled"] is True

    users = await client.get("/api/auth/organization/users", headers=org["headers"])
    assert users.status_code == 200
    assert users.json()["pending_invitations"] == []
