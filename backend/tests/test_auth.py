from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.csrf import EXEMPT_PATHS, _is_exempt_path
from app.core.security import create_refresh_token, generate_totp_code, hash_password
from app.db.models.refresh_token import RefreshToken
from app.db.models.user import User
from app.main import app
from app.repositories.refresh_token_repo import RefreshTokenRepository
from tests.conftest import TestSessionLocal

TRUSTED_TEST_ORIGIN = "http://test"
UNTRUSTED_TEST_ORIGIN = "https://evil.example"


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


def _trusted_cookie_headers(csrf_token: str) -> dict[str, str]:
    return {
        "Origin": TRUSTED_TEST_ORIGIN,
        "X-CSRF-Token": csrf_token,
    }


def _browser_auth_headers(csrf_token: str | None = None) -> dict[str, str]:
    headers = {
        "Origin": TRUSTED_TEST_ORIGIN,
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
    }
    if csrf_token:
        headers["X-CSRF-Token"] = csrf_token
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
    assert "refresh_token" not in data
    assert data["token_type"] == "bearer"
    assert resp.cookies.get("access_token")
    assert resp.cookies.get("csrf_token")
    assert resp.cookies.get("refresh_token")


@pytest.mark.asyncio
async def test_browser_login_uses_cookie_only_response(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={
            "email": "browser-login@example.com",
            "password": "password123",
            "full_name": "Browser Login",
        },
    )

    resp = await client.post(
        "/api/auth/login",
        json={"email": "browser-login@example.com", "password": "password123"},
        headers=_browser_auth_headers(),
    )

    assert resp.status_code == 200
    assert resp.json()["token_type"] == "bearer"
    assert resp.json()["session_mode"] == "cookie"
    assert "access_token" not in resp.json()
    assert resp.cookies.get("access_token")
    assert resp.cookies.get("refresh_token")


def test_csrf_exempt_paths_allowlist_snapshot():
    assert EXEMPT_PATHS == {
        "/api/auth/login",
        "/api/auth/register",
    }
    assert _is_exempt_path("/api/auth/login") is True
    assert _is_exempt_path("/api/auth/register") is True
    assert _is_exempt_path("/api/auth/sso/providers/google/start") is True
    assert _is_exempt_path("/api/auth/sso/providers/google/callback") is True
    assert _is_exempt_path("/api/auth/refresh") is False
    assert _is_exempt_path("/api/auth/logout") is False
    assert _is_exempt_path("/api/auth/change-password") is False


@pytest.mark.asyncio
async def test_refresh_token_is_hashed_at_rest(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={
            "email": "refresh-hash@example.com",
            "password": "password123",
            "full_name": "Refresh Hash",
        },
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": "refresh-hash@example.com", "password": "password123"},
    )
    refresh_cookie = login.cookies.get("refresh_token")
    assert refresh_cookie

    async with TestSessionLocal() as session:
        stored = (
            await session.execute(select(RefreshToken).where(RefreshToken.user_id == 1))
        ).scalar_one()

    assert stored.token != refresh_cookie
    assert len(stored.token) == 64
    assert all(char in "0123456789abcdef" for char in stored.token)


@pytest.mark.asyncio
async def test_refresh_lookup_auto_migrates_legacy_raw_token_row():
    legacy_refresh = create_refresh_token(1, "legacy-refresh@example.com")

    async with TestSessionLocal() as session:
        user = User(
            id=1,
            email="legacy-refresh@example.com",
            password_hash=hash_password("password123"),
            full_name="Legacy Refresh",
            is_active=True,
        )
        session.add(user)
        session.add(
            RefreshToken(
                user_id=1,
                token=legacy_refresh,
                token_jti=None,
                expires_at=datetime.now(UTC) + timedelta(days=7),
            )
        )
        await session.commit()

    async with TestSessionLocal() as session:
        repo = RefreshTokenRepository(session)
        refresh_session = await repo.get_active_by_token(legacy_refresh)
        assert refresh_session is not None
        assert refresh_session.token != legacy_refresh
        assert len(refresh_session.token) == 64
        assert refresh_session.token_jti is not None
        await session.commit()

    async with TestSessionLocal() as session:
        stored = (
            await session.execute(select(RefreshToken).where(RefreshToken.user_id == 1))
        ).scalar_one()
    assert stored.token != legacy_refresh
    assert len(stored.token) == 64
    assert stored.token_jti is not None


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
async def test_me_with_access_cookie_returns_user(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={
            "email": "cookie-auth@example.com",
            "password": "password123",
            "full_name": "Cookie Auth",
        },
    )
    await client.post(
        "/api/auth/login",
        json={"email": "cookie-auth@example.com", "password": "password123"},
    )

    resp = await client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "cookie-auth@example.com"


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
    assert original.json()["legal_name"] is None
    assert original.json()["registration_number"] is None
    assert original.json()["jurisdiction"] is None
    assert original.json()["default_standards"] == []
    assert original.json()["consolidation_approach"] is None
    assert original.json()["ghg_scope_approach"] is None
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
            "legal_name": "Settings Org Holdings Ltd",
            "registration_number": "UK-999",
            "country": "DE",
            "jurisdiction": "Germany",
            "industry": "energy",
            "currency": "EUR",
            "reporting_year": 2026,
            "default_standards": ["GRI"],
            "consolidation_approach": "financial_control",
            "ghg_scope_approach": "market_based",
            "default_boundary_id": second_boundary.json()["id"],
        },
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Settings Org Updated"
    assert updated.json()["legal_name"] == "Settings Org Holdings Ltd"
    assert updated.json()["registration_number"] == "UK-999"
    assert updated.json()["country"] == "DE"
    assert updated.json()["jurisdiction"] == "Germany"
    assert updated.json()["industry"] == "energy"
    assert updated.json()["currency"] == "EUR"
    assert updated.json()["reporting_year"] == 2026
    assert updated.json()["default_standards"] == ["GRI"]
    assert updated.json()["consolidation_approach"] == "financial_control"
    assert updated.json()["ghg_scope_approach"] == "market_based"
    assert updated.json()["default_boundary_id"] == second_boundary.json()["id"]


@pytest.mark.asyncio
async def test_organization_context_cookie_allows_tenant_requests_without_header(
    client: AsyncClient,
):
    headers = await _setup_org_context(client, email="org-cookie@example.com")
    project = await client.post(
        "/api/projects",
        json={"name": "Cookie Scoped Project"},
        headers=headers,
    )
    assert project.status_code == 201

    context = await client.post(
        "/api/auth/context/organization",
        json={"organization_id": int(headers["X-Organization-Id"])},
        headers={"Authorization": headers["Authorization"]},
    )
    assert context.status_code == 200
    assert context.cookies.get("current_organization_id") == headers["X-Organization-Id"]

    resp = await client.get(
        "/api/projects",
        headers={"Authorization": headers["Authorization"]},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["id"] == project.json()["id"]


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
    csrf_token = login_resp.cookies.get("csrf_token")
    assert csrf_token
    original_refresh_cookie = login_resp.cookies.get("refresh_token")
    assert original_refresh_cookie

    resp = await client.post(
        "/api/auth/refresh",
        headers=_browser_auth_headers(csrf_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_mode"] == "cookie"
    assert "access_token" not in data
    assert "refresh_token" not in data
    assert resp.cookies.get("access_token")
    rotated_refresh_cookie = resp.cookies.get("refresh_token")
    assert rotated_refresh_cookie
    assert rotated_refresh_cookie != original_refresh_cookie


@pytest.mark.asyncio
async def test_refresh_token_accepts_body_fallback(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={
            "email": "refresh-body@example.com",
            "password": "password123",
            "full_name": "Refresh Body",
        },
    )
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": "refresh-body@example.com", "password": "password123"},
    )
    refresh_token = login_resp.cookies.get("refresh_token")
    csrf_token = login_resp.cookies.get("csrf_token")
    assert refresh_token
    assert csrf_token

    client.cookies.clear()
    resp = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_token},
        headers=_browser_auth_headers(csrf_token),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["session_mode"] == "cookie"
    assert "access_token" not in data
    assert "refresh_token" not in data
    assert resp.cookies.get("access_token")
    assert resp.cookies.get("refresh_token")


@pytest.mark.asyncio
async def test_logout_invalidates_tokens(client: AsyncClient, auth_headers: dict):
    assert client.cookies.get("access_token")
    assert client.cookies.get("csrf_token")
    assert client.cookies.get("refresh_token")
    resp = await client.post("/api/auth/logout", headers=auth_headers)
    assert resp.status_code == 204
    assert client.cookies.get("access_token") is None
    assert client.cookies.get("csrf_token") is None
    assert client.cookies.get("refresh_token") is None


@pytest.mark.asyncio
async def test_list_sessions_marks_current_session(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={
            "email": "sessions@example.com",
            "password": "password123",
            "full_name": "Session User",
        },
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": "sessions@example.com", "password": "password123"},
        headers={"User-Agent": "pytest-session-browser"},
    )
    assert login.status_code == 200

    sessions = await client.get("/api/auth/sessions")
    assert sessions.status_code == 200
    payload = sessions.json()
    assert payload["total"] == 1
    assert payload["items"][0]["is_current"] is True
    assert payload["items"][0]["user_agent"] == "pytest-session-browser"


@pytest.mark.asyncio
async def test_logout_only_revokes_current_session(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={
            "email": "two-sessions@example.com",
            "password": "password123",
            "full_name": "Two Sessions",
        },
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as second_client:
        first_login = await client.post(
            "/api/auth/login",
            json={"email": "two-sessions@example.com", "password": "password123"},
        )
        first_access_token = first_login.json()["access_token"]
        second_login = await second_client.post(
            "/api/auth/login",
            json={"email": "two-sessions@example.com", "password": "password123"},
        )
        second_access_token = second_login.json()["access_token"]
        first_csrf = first_login.cookies.get("csrf_token")
        second_csrf = second_login.cookies.get("csrf_token")
        assert first_csrf
        assert second_csrf

        before = await client.get("/api/auth/sessions")
        assert before.status_code == 200
        assert before.json()["total"] == 2

        logout = await client.post(
            "/api/auth/logout",
            headers=_trusted_cookie_headers(first_csrf),
        )
        assert logout.status_code == 204

        first_refresh = await client.post(
            "/api/auth/refresh",
            headers=_trusted_cookie_headers(first_csrf),
        )
        assert first_refresh.status_code == 401

        first_me = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {first_access_token}"},
        )
        assert first_me.status_code == 401

        second_refresh = await second_client.post(
            "/api/auth/refresh",
            headers=_trusted_cookie_headers(second_csrf),
        )
        assert second_refresh.status_code == 200
        rotated_second_access_token = second_client.cookies.get("access_token")
        assert rotated_second_access_token
        rotated_second_me = await second_client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {rotated_second_access_token}"},
        )
        stale_second_me = await second_client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {second_access_token}"},
        )
        assert rotated_second_me.status_code == 200
        assert stale_second_me.status_code == 401


@pytest.mark.asyncio
async def test_logout_all_revokes_every_session(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={
            "email": "logout-all@example.com",
            "password": "password123",
            "full_name": "Logout All",
        },
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as second_client:
        first_login = await client.post(
            "/api/auth/login",
            json={"email": "logout-all@example.com", "password": "password123"},
        )
        first_access_token = first_login.json()["access_token"]
        second_login = await second_client.post(
            "/api/auth/login",
            json={"email": "logout-all@example.com", "password": "password123"},
        )
        second_access_token = second_login.json()["access_token"]
        csrf_token = first_login.cookies.get("csrf_token")
        second_csrf = second_login.cookies.get("csrf_token")
        assert csrf_token
        assert second_csrf

        logout_all = await client.post(
            "/api/auth/logout-all",
            headers=_trusted_cookie_headers(csrf_token),
        )
        assert logout_all.status_code == 200
        assert logout_all.json()["revoked_sessions"] == 2

        second_refresh = await second_client.post(
            "/api/auth/refresh",
            headers=_trusted_cookie_headers(second_csrf),
        )
        assert second_refresh.status_code == 401

        first_me = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {first_access_token}"},
        )
        second_me = await second_client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {second_access_token}"},
        )
        assert first_me.status_code == 401
        assert second_me.status_code == 401


@pytest.mark.asyncio
async def test_revoke_specific_session_blocks_that_client_only(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={
            "email": "revoke-session@example.com",
            "password": "password123",
            "full_name": "Revoke Session",
        },
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as second_client:
        primary_login = await client.post(
            "/api/auth/login",
            json={"email": "revoke-session@example.com", "password": "password123"},
            headers={"User-Agent": "primary-client"},
        )
        primary_access_token = primary_login.json()["access_token"]
        second_login = await second_client.post(
            "/api/auth/login",
            json={"email": "revoke-session@example.com", "password": "password123"},
            headers={"User-Agent": "secondary-client"},
        )
        secondary_access_token = second_login.json()["access_token"]
        second_csrf = second_login.cookies.get("csrf_token")
        assert second_csrf

        sessions = await client.get("/api/auth/sessions")
        session_items = sessions.json()["items"]
        secondary_session = next(
            item for item in session_items if item["user_agent"] == "secondary-client"
        )

        revoked = await client.delete(
            f"/api/auth/sessions/{secondary_session['id']}",
            headers=_trusted_cookie_headers(client.cookies.get("csrf_token")),
        )
        assert revoked.status_code == 200
        assert revoked.json()["revoked"] is True
        assert revoked.json()["is_current"] is False

        second_refresh = await second_client.post(
            "/api/auth/refresh",
            headers=_trusted_cookie_headers(second_csrf),
        )
        assert second_refresh.status_code == 401

        primary_me = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {primary_access_token}"},
        )
        secondary_me = await second_client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {secondary_access_token}"},
        )
        assert primary_me.status_code == 200
        assert secondary_me.status_code == 401


@pytest.mark.asyncio
async def test_change_password_preserves_current_session_and_revokes_others(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={
            "email": "password-rotation@example.com",
            "password": "password123",
            "full_name": "Password Rotation",
        },
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as second_client:
        first_login = await client.post(
            "/api/auth/login",
            json={"email": "password-rotation@example.com", "password": "password123"},
        )
        first_access_token = first_login.json()["access_token"]
        second_login = await second_client.post(
            "/api/auth/login",
            json={"email": "password-rotation@example.com", "password": "password123"},
        )
        second_access_token = second_login.json()["access_token"]
        second_csrf = second_login.cookies.get("csrf_token")
        assert first_login.cookies.get("csrf_token")
        assert second_csrf

        changed = await client.post(
            "/api/auth/change-password",
            json={"current_password": "password123", "new_password": "newpassword123"},
            headers=_trusted_cookie_headers(first_login.cookies.get("csrf_token")),
        )
        assert changed.status_code == 200
        assert changed.json()["changed"] is True
        assert changed.json()["current_session_preserved"] is True
        assert changed.json()["revoked_sessions"] == 1

        me = await client.get("/api/auth/me")
        assert me.status_code == 200

        second_refresh = await second_client.post(
            "/api/auth/refresh",
            headers=_trusted_cookie_headers(second_csrf),
        )
        assert second_refresh.status_code == 401

        first_me = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {first_access_token}"},
        )
        second_me = await second_client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {second_access_token}"},
        )
        assert first_me.status_code == 200
        assert second_me.status_code == 401


@pytest.mark.asyncio
async def test_cookie_authenticated_write_requires_csrf_header(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={"email": "csrf@example.com", "password": "password123", "full_name": "CSRF User"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": "csrf@example.com", "password": "password123"},
    )
    csrf_token = login.cookies.get("csrf_token")
    assert csrf_token

    blocked = await client.patch(
        "/api/auth/me",
        json={"full_name": "Blocked Update"},
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "CSRF_VALIDATION_FAILED"

    allowed = await client.patch(
        "/api/auth/me",
        json={"full_name": "Allowed Update"},
        headers=_trusted_cookie_headers(csrf_token),
    )
    assert allowed.status_code == 200
    assert allowed.json()["full_name"] == "Allowed Update"


@pytest.mark.asyncio
async def test_cookie_authenticated_write_requires_trusted_origin_or_referer(
    client: AsyncClient,
):
    await client.post(
        "/api/auth/register",
        json={
            "email": "origin@example.com",
            "password": "password123",
            "full_name": "Origin User",
        },
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": "origin@example.com", "password": "password123"},
    )
    csrf_token = login.cookies.get("csrf_token")
    assert csrf_token

    blocked = await client.patch(
        "/api/auth/me",
        json={"full_name": "Blocked Origin Update"},
        headers={
            "Origin": UNTRUSTED_TEST_ORIGIN,
            "X-CSRF-Token": csrf_token,
        },
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "ORIGIN_VALIDATION_FAILED"

    allowed = await client.patch(
        "/api/auth/me",
        json={"full_name": "Allowed Referer Update"},
        headers={
            "Referer": f"{TRUSTED_TEST_ORIGIN}/settings/profile",
            "X-CSRF-Token": csrf_token,
        },
    )
    assert allowed.status_code == 200
    assert allowed.json()["full_name"] == "Allowed Referer Update"


@pytest.mark.asyncio
async def test_cookie_authenticated_write_rejects_cross_site_fetch_metadata(
    client: AsyncClient,
):
    await client.post(
        "/api/auth/register",
        json={
            "email": "fetch-metadata@example.com",
            "password": "password123",
            "full_name": "Fetch Metadata User",
        },
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": "fetch-metadata@example.com", "password": "password123"},
    )
    csrf_token = login.cookies.get("csrf_token")
    assert csrf_token

    blocked = await client.patch(
        "/api/auth/me",
        json={"full_name": "Blocked Cross Site"},
        headers={
            "Origin": TRUSTED_TEST_ORIGIN,
            "Sec-Fetch-Site": "cross-site",
            "X-CSRF-Token": csrf_token,
        },
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "FETCH_METADATA_VALIDATION_FAILED"

    allowed = await client.patch(
        "/api/auth/me",
        json={"full_name": "Allowed Same Origin"},
        headers={
            "Origin": TRUSTED_TEST_ORIGIN,
            "Sec-Fetch-Site": "same-origin",
            "X-CSRF-Token": csrf_token,
        },
    )
    assert allowed.status_code == 200
    assert allowed.json()["full_name"] == "Allowed Same Origin"


@pytest.mark.asyncio
async def test_bearer_authenticated_write_does_not_require_csrf_header(client: AsyncClient):
    headers = await _setup_org_context(client, email="csrf-bearer@example.com")

    updated = await client.patch(
        "/api/auth/me",
        json={"full_name": "Bearer Update"},
        headers={"Authorization": headers["Authorization"]},
    )
    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Bearer Update"


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
