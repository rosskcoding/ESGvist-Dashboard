"""
Integration tests for cookie-based auth (refresh token rotation + revocation).

These tests run the FastAPI app in-process (ASGI) but DO NOT bypass auth.
We only override DB session dependency to reuse the per-test transaction.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Company, CompanyMembership, RefreshToken, User
from app.infra.database import get_session
from app.main import create_app
from app.middleware.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.services.auth import decode_token, hash_password


REFRESH_COOKIE = "refresh_token"


@pytest_asyncio.fixture
async def app_real_auth(db_session: AsyncSession):
    """
    FastAPI app with real auth (no dependency override for get_current_user_required).

    We only override DB session to use the per-test `db_session` provided by conftest.
    """
    app = create_app()

    async def _override_get_session():
        try:
            yield db_session
            await db_session.flush()
        except Exception:
            await db_session.rollback()
            raise

    app.dependency_overrides[get_session] = _override_get_session
    return app


@pytest_asyncio.fixture
async def real_client(app_real_auth) -> AsyncClient:
    transport = ASGITransport(app=app_real_auth)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def seeded_user(db_session: AsyncSession) -> tuple[User, str]:
    """
    Create a real user with password + company membership for login tests.

    Returns: (user, plain_password)
    """
    password = "TestPassword123!"

    company = Company(name=f"Auth Test Company {uuid4()}")
    db_session.add(company)
    await db_session.flush()

    user = User(
        email=f"auth-user-{uuid4()}@example.com",
        full_name="Auth Test User",
        password_hash=hash_password(password),
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.flush()

    membership = CompanyMembership(
        company_id=company.company_id,
        user_id=user.user_id,
        is_active=True,
    )
    db_session.add(membership)
    await db_session.flush()

    return user, password


def _extract_set_cookie(headers: dict[str, str]) -> str:
    # httpx folds multiple Set-Cookie headers; this keeps it simple for our assertions.
    return headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_login_sets_refresh_cookie_and_creates_refresh_token_row(
    real_client: AsyncClient,
    db_session: AsyncSession,
    seeded_user: tuple[User, str],
):
    user, password = seeded_user

    resp = await real_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"] == ""
    assert body["user"]["email"] == user.email

    set_cookie = _extract_set_cookie(resp.headers)
    assert f"{REFRESH_COOKIE}=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/api/v1/auth" in set_cookie

    refresh_jwt = real_client.cookies.get(REFRESH_COOKIE)
    assert refresh_jwt, "httpx client cookie jar should store refresh_token"

    payload = decode_token(refresh_jwt)
    assert payload is not None
    assert payload["type"] == "refresh"
    assert payload["sub"] == str(user.user_id)
    assert payload.get("jti")

    token_row = (
        await db_session.execute(select(RefreshToken).where(RefreshToken.jti == payload["jti"]))
    ).scalar_one_or_none()
    assert token_row is not None
    assert token_row.user_id == user.user_id
    assert token_row.is_used is False
    assert token_row.is_revoked is False


@pytest.mark.asyncio
async def test_refresh_rotates_cookie_and_marks_old_token_used(
    real_client: AsyncClient,
    db_session: AsyncSession,
    seeded_user: tuple[User, str],
):
    user, password = seeded_user

    # Login: get initial refresh cookie A
    login = await real_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    assert login.status_code == 200, login.text

    refresh_a = real_client.cookies.get(REFRESH_COOKIE)
    assert refresh_a
    payload_a = decode_token(refresh_a)
    assert payload_a and payload_a["type"] == "refresh"
    jti_a = payload_a["jti"]

    row_a = (
        await db_session.execute(select(RefreshToken).where(RefreshToken.jti == jti_a))
    ).scalar_one()
    assert row_a.is_used is False
    assert row_a.is_revoked is False

    # Refresh: should rotate to cookie B and mark A as used
    csrf_token = real_client.cookies.get(CSRF_COOKIE_NAME)
    assert csrf_token, "Expected csrf_token cookie after login"
    refreshed = await real_client.post(
        "/api/v1/auth/refresh",
        json={},
        headers={CSRF_HEADER_NAME: csrf_token},
    )
    assert refreshed.status_code == 200, refreshed.text

    refresh_b = real_client.cookies.get(REFRESH_COOKIE)
    assert refresh_b
    assert refresh_b != refresh_a
    payload_b = decode_token(refresh_b)
    assert payload_b and payload_b["type"] == "refresh"
    jti_b = payload_b["jti"]

    await db_session.refresh(row_a)
    assert row_a.is_used is True
    assert row_a.is_revoked is False

    row_b = (
        await db_session.execute(select(RefreshToken).where(RefreshToken.jti == jti_b))
    ).scalar_one()
    assert row_b.is_used is False
    assert row_b.is_revoked is False
    assert row_b.family_id == row_a.family_id


@pytest.mark.asyncio
async def test_refresh_reuse_old_token_revokes_family_and_returns_401(
    real_client: AsyncClient,
    db_session: AsyncSession,
    seeded_user: tuple[User, str],
):
    user, password = seeded_user

    # Login -> cookie A
    login = await real_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    assert login.status_code == 200
    refresh_a = real_client.cookies.get(REFRESH_COOKIE)
    assert refresh_a
    payload_a = decode_token(refresh_a)
    assert payload_a and payload_a["type"] == "refresh"
    jti_a = payload_a["jti"]

    # Refresh once -> cookie B, A becomes used
    csrf_token = real_client.cookies.get(CSRF_COOKIE_NAME)
    assert csrf_token, "Expected csrf_token cookie after login"
    refreshed = await real_client.post(
        "/api/v1/auth/refresh",
        json={},
        headers={CSRF_HEADER_NAME: csrf_token},
    )
    assert refreshed.status_code == 200

    # Fetch family_id via DB (by jti A)
    row_a = (
        await db_session.execute(select(RefreshToken).where(RefreshToken.jti == jti_a))
    ).scalar_one()
    family_id = row_a.family_id
    assert row_a.is_used is True

    # Try to reuse OLD token A -> should be detected and rejected
    # CSRF token may have been rotated by the previous refresh.
    csrf_token = real_client.cookies.get(CSRF_COOKIE_NAME)
    assert csrf_token, "Expected csrf_token cookie after refresh"
    reuse = await real_client.post(
        "/api/v1/auth/refresh",
        json={},
        cookies={REFRESH_COOKIE: refresh_a},
        headers={CSRF_HEADER_NAME: csrf_token},
    )
    assert reuse.status_code == 401

    # Family should be revoked (including the latest token)
    family_rows = list(
        (await db_session.execute(select(RefreshToken).where(RefreshToken.family_id == family_id)))
        .scalars()
        .all()
    )
    assert family_rows, "Expected at least one refresh token row in the family"
    assert all(r.is_revoked for r in family_rows)


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token_and_refresh_fails_after(
    real_client: AsyncClient,
    db_session: AsyncSession,
    seeded_user: tuple[User, str],
):
    user, password = seeded_user

    login = await real_client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    assert login.status_code == 200
    access_token = login.json()["access_token"]
    refresh_jwt = real_client.cookies.get(REFRESH_COOKIE)
    assert refresh_jwt
    payload = decode_token(refresh_jwt)
    assert payload and payload.get("jti")
    csrf_token = real_client.cookies.get(CSRF_COOKIE_NAME)
    assert csrf_token, "Expected csrf_token cookie after login"

    # Logout should revoke the current refresh token (by cookie jti)
    logout = await real_client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert logout.status_code == 204, logout.text

    token_row = (
        await db_session.execute(select(RefreshToken).where(RefreshToken.jti == payload["jti"]))
    ).scalar_one()
    assert token_row.is_revoked is True

    # Even if attacker kept the old cookie value, refresh must fail
    refresh_after = await real_client.post(
        "/api/v1/auth/refresh",
        json={},
        cookies={REFRESH_COOKIE: refresh_jwt, CSRF_COOKIE_NAME: csrf_token},
        headers={CSRF_HEADER_NAME: csrf_token},
    )
    assert refresh_after.status_code == 401


