import pytest
from httpx import AsyncClient

from app.core.security import generate_totp_code


async def _setup_org_context(client: AsyncClient, *, email: str = "org-admin@example.com") -> dict:
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123", "full_name": "Org Admin"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    org = await client.post(
        "/api/organizations/setup",
        json={"name": "Settings Org", "country": "GB"},
        headers=headers,
    )
    headers["X-Organization-Id"] = str(org.json()["organization_id"])
    return headers


@pytest.mark.asyncio
async def test_register_creates_user(client: AsyncClient):
    resp = await client.post(
        "/api/auth/register",
        json={"email": "new@example.com", "password": "password123", "full_name": "New User"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "new@example.com"
    assert data["full_name"] == "New User"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_first_user_gets_platform_admin(client: AsyncClient):
    resp = await client.post(
        "/api/auth/register",
        json={"email": "first@example.com", "password": "password123", "full_name": "First User"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["roles"]) == 1
    assert data["roles"][0]["role"] == "platform_admin"
    assert data["roles"][0]["scope_type"] == "platform"
    assert data["roles"][0]["scope_id"] is None


@pytest.mark.asyncio
async def test_duplicate_email_returns_409(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={"email": "dup@example.com", "password": "password123", "full_name": "User 1"},
    )
    resp = await client.post(
        "/api/auth/register",
        json={"email": "dup@example.com", "password": "password123", "full_name": "User 2"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_login_returns_tokens(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={"email": "login@example.com", "password": "password123", "full_name": "Login User"},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"email": "login@example.com", "password": "password123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_credentials_returns_401(client: AsyncClient):
    resp = await client.post(
        "/api/auth/login",
        json={"email": "noone@example.com", "password": "wrong"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_me_without_token_returns_401_or_403(client: AsyncClient):
    resp = await client.get("/api/auth/me")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_me_with_token_returns_user(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "test@example.com"
    assert data["full_name"] == "Test User"


@pytest.mark.asyncio
async def test_update_me_and_change_password(client: AsyncClient):
    headers = await _setup_org_context(client, email="profile@example.com")

    updated = await client.patch(
        "/api/auth/me",
        json={"full_name": "Updated Profile User"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Updated Profile User"
    assert updated.json()["organization_name"] == "Settings Org"

    changed = await client.post(
        "/api/auth/change-password",
        json={"current_password": "password123", "new_password": "newpassword123"},
        headers=headers,
    )
    assert changed.status_code == 200
    assert changed.json()["changed"] is True

    relogin = await client.post(
        "/api/auth/login",
        json={"email": "profile@example.com", "password": "newpassword123"},
    )
    assert relogin.status_code == 200


@pytest.mark.asyncio
async def test_get_and_update_my_organization_settings(client: AsyncClient):
    headers = await _setup_org_context(client, email="settings@example.com")

    original = await client.get("/api/auth/me/organization", headers=headers)
    assert original.status_code == 200
    assert original.json()["name"] == "Settings Org"
    assert original.json()["default_boundary_id"] is not None

    second_boundary = await client.post(
        "/api/boundaries",
        json={"name": "Secondary Boundary", "boundary_type": "custom"},
        headers=headers,
    )
    assert second_boundary.status_code == 201

    updated = await client.patch(
        "/api/auth/me/organization",
        json={
            "name": "Settings Org Updated",
            "country": "DE",
            "industry": "energy",
            "currency": "EUR",
            "reporting_year": 2026,
            "default_boundary_id": second_boundary.json()["id"],
        },
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Settings Org Updated"
    assert updated.json()["country"] == "DE"
    assert updated.json()["industry"] == "energy"
    assert updated.json()["currency"] == "EUR"
    assert updated.json()["reporting_year"] == 2026
    assert updated.json()["default_boundary_id"] == second_boundary.json()["id"]


@pytest.mark.asyncio
async def test_refresh_token_rotation(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={"email": "refresh@example.com", "password": "password123", "full_name": "Refresh"},
    )
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": "refresh@example.com", "password": "password123"},
    )
    refresh_token = login_resp.json()["refresh_token"]

    resp = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data  # new refresh token issued


@pytest.mark.asyncio
async def test_logout_invalidates_tokens(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/auth/logout", headers=auth_headers)
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_error_response_format(client: AsyncClient):
    resp = await client.post(
        "/api/auth/login",
        json={"email": "x@x.com", "password": "wrong"},
    )
    data = resp.json()
    assert "error" in data
    assert "code" in data["error"]
    assert "message" in data["error"]
    assert "requestId" in data["error"]


@pytest.mark.asyncio
async def test_two_factor_setup_enable_and_login(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={"email": "2fa@example.com", "password": "password123", "full_name": "Two Factor"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": "2fa@example.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    setup = await client.post("/api/auth/2fa/setup", headers=headers)
    assert setup.status_code == 200
    secret = setup.json()["secret"]
    assert len(setup.json()["backup_codes"]) == 8

    status_before = await client.get("/api/auth/2fa/status", headers=headers)
    assert status_before.status_code == 200
    assert status_before.json()["pending_setup"] is True
    assert status_before.json()["enabled"] is False

    enable = await client.post(
        "/api/auth/2fa/enable",
        json={"code": generate_totp_code(secret)},
        headers=headers,
    )
    assert enable.status_code == 200
    assert enable.json()["enabled"] is True
    assert enable.json()["backup_codes_remaining"] == 8

    blocked = await client.post(
        "/api/auth/login",
        json={"email": "2fa@example.com", "password": "password123"},
    )
    assert blocked.status_code == 401
    assert blocked.json()["error"]["code"] == "TWO_FACTOR_REQUIRED"

    allowed = await client.post(
        "/api/auth/login",
        json={
            "email": "2fa@example.com",
            "password": "password123",
            "totp_code": generate_totp_code(secret),
        },
    )
    assert allowed.status_code == 200
    assert "access_token" in allowed.json()


@pytest.mark.asyncio
async def test_two_factor_backup_code_can_be_used_once(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={"email": "backup@example.com", "password": "password123", "full_name": "Backup User"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": "backup@example.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    setup = await client.post("/api/auth/2fa/setup", headers=headers)
    secret = setup.json()["secret"]
    backup_code = setup.json()["backup_codes"][0]

    enable = await client.post(
        "/api/auth/2fa/enable",
        json={"code": generate_totp_code(secret)},
        headers=headers,
    )
    assert enable.status_code == 200

    first = await client.post(
        "/api/auth/login",
        json={
            "email": "backup@example.com",
            "password": "password123",
            "backup_code": backup_code,
        },
    )
    assert first.status_code == 200

    second = await client.post(
        "/api/auth/login",
        json={
            "email": "backup@example.com",
            "password": "password123",
            "backup_code": backup_code,
        },
    )
    assert second.status_code == 401
    assert second.json()["error"]["code"] == "TWO_FACTOR_REQUIRED"
