import pytest
from httpx import AsyncClient


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
