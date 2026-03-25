import pytest
from httpx import AsyncClient

from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.repositories.audit_repo import AuditRepository
from app.repositories.refresh_token_repo import RefreshTokenRepository
from app.repositories.role_binding_repo import RoleBindingRepository
from app.repositories.sso_repo import SSORepository
from app.repositories.user_repo import UserRepository
from app.services.sso_service import SSOService
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
    return {"headers": {"Authorization": f"Bearer {login.json()['access_token']}"}}


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
    user_headers = {
        **user["headers"],
        "X-Organization-Id": admin_headers["X-Organization-Id"],
    }
    accepted = await client.post(
        f"/api/invitations/accept/{invitation.json()['token']}",
        headers=user_headers,
    )
    assert accepted.status_code == 200
    return {
        "headers": user["headers"],
        "tenant_headers": user_headers,
    }


async def _create_provider(
    client: AsyncClient,
    tenant_headers: dict,
    *,
    name: str = "Corporate SSO",
) -> int:
    created = await client.post(
        "/api/auth/sso/providers",
        json={
            "name": name,
            "provider_type": "oauth2",
            "auth_url": "https://login.example.com/oauth/authorize",
            "issuer": "https://login.example.com/",
            "client_id": f"{name.lower().replace(' ', '-')}-client",
            "client_secret": "secret-456",
            "redirect_uri": "https://app.example.com/auth/callback",
            "default_role": "reviewer",
            "auto_provision": True,
        },
        headers=tenant_headers,
    )
    assert created.status_code == 201
    return created.json()["id"]


@pytest.fixture
async def sso_ctx(client: AsyncClient) -> dict:
    admin = await _register_and_login(client, email="sso-admin@test.com", full_name="SSO Admin")
    org = await client.post(
        "/api/organizations/setup",
        json={"name": "SSO Org", "country": "GB"},
        headers=admin["headers"],
    )
    tenant_headers = {
        **admin["headers"],
        "X-Organization-Id": str(org.json()["organization_id"]),
    }
    return {
        "tenant_headers": tenant_headers,
        "org_id": org.json()["organization_id"],
    }


@pytest.mark.asyncio
async def test_sso_provider_can_be_created_and_listed_publicly(client: AsyncClient, sso_ctx: dict):
    created = await client.post(
        "/api/auth/sso/providers",
        json={
            "name": "Microsoft Entra ID",
            "provider_type": "oauth2",
            "auth_url": "https://login.example.com/oauth/authorize",
            "issuer": "https://login.example.com/",
            "client_id": "client-123",
            "client_secret": "secret-123",
            "redirect_uri": "https://app.example.com/auth/callback",
            "default_role": "collector",
            "auto_provision": True,
        },
        headers=sso_ctx["tenant_headers"],
    )
    assert created.status_code == 201
    data = created.json()
    assert data["name"] == "Microsoft Entra ID"
    assert data["secret_configured"] is True

    public = await client.get(
        "/api/auth/sso/providers",
        params={"organization_id": sso_ctx["org_id"]},
    )
    assert public.status_code == 200
    assert public.json()["total"] == 1
    assert public.json()["items"][0]["provider_type"] == "oauth2"


@pytest.mark.asyncio
async def test_sso_start_and_callback_auto_provision_user(client: AsyncClient, sso_ctx: dict):
    provider_id = await _create_provider(client, sso_ctx["tenant_headers"])

    started = await client.post(
        f"/api/auth/sso/providers/{provider_id}/start",
        json={"organization_id": sso_ctx["org_id"]},
    )
    assert started.status_code == 200
    assert started.json()["provider_id"] == provider_id
    assert "state=" in started.json()["auth_url"]

    callback = await client.post(
        f"/api/auth/sso/providers/{provider_id}/callback",
        json={
            "state": started.json()["state"],
            "email": "sso-user@test.com",
            "full_name": "SSO User",
            "external_subject": "entra|user-123",
        },
    )
    assert callback.status_code == 200
    assert callback.cookies.get("access_token")
    assert "refresh_token" not in callback.json()
    assert callback.cookies.get("refresh_token")
    token = callback.json()["access_token"]

    me = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == "sso-user@test.com"

    projects = await client.get(
        "/api/projects",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Organization-Id": str(sso_ctx["org_id"]),
        },
    )
    assert projects.status_code == 200


@pytest.mark.asyncio
async def test_browser_sso_callback_uses_cookie_only_response(client: AsyncClient, sso_ctx: dict):
    provider_id = await _create_provider(client, sso_ctx["tenant_headers"], name="Browser SSO")

    started = await client.post(
        f"/api/auth/sso/providers/{provider_id}/start",
        json={"organization_id": sso_ctx["org_id"]},
    )
    assert started.status_code == 200

    callback = await client.post(
        f"/api/auth/sso/providers/{provider_id}/callback",
        json={
            "state": started.json()["state"],
            "email": "browser-sso@test.com",
            "full_name": "Browser SSO",
            "external_subject": "oauth|browser-sso",
        },
        headers={
            "Origin": "http://test",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
        },
    )
    assert callback.status_code == 200
    assert callback.json()["session_mode"] == "cookie"
    assert "access_token" not in callback.json()
    assert callback.cookies.get("access_token")
    assert callback.cookies.get("refresh_token")

    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "browser-sso@test.com"


@pytest.mark.asyncio
async def test_sso_state_is_single_use(client: AsyncClient, sso_ctx: dict):
    created = await client.post(
        "/api/auth/sso/providers",
        json={
            "name": "Single Use SSO",
            "provider_type": "saml2",
            "auth_url": "https://login.example.com/saml/init",
            "issuer": "https://login.example.com/saml",
            "client_id": "client-789",
            "redirect_uri": "https://app.example.com/auth/callback",
            "default_role": "collector",
            "auto_provision": True,
        },
        headers=sso_ctx["tenant_headers"],
    )
    provider_id = created.json()["id"]

    started = await client.post(
        f"/api/auth/sso/providers/{provider_id}/start",
        json={"organization_id": sso_ctx["org_id"]},
    )
    state = started.json()["state"]

    first = await client.post(
        f"/api/auth/sso/providers/{provider_id}/callback",
        json={
            "state": state,
            "email": "single-use@test.com",
            "full_name": "Single Use",
            "external_subject": "saml|abc",
        },
    )
    assert first.status_code == 200

    second = await client.post(
        f"/api/auth/sso/providers/{provider_id}/callback",
        json={
            "state": state,
            "email": "single-use@test.com",
            "full_name": "Single Use",
            "external_subject": "saml|abc",
        },
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "SSO_STATE_USED"


@pytest.mark.asyncio
async def test_login_options_and_auth_settings_require_active_provider(
    client: AsyncClient,
    sso_ctx: dict,
):
    options = await client.get(
        "/api/auth/login-options",
        params={"organization_id": sso_ctx["org_id"]},
    )
    assert options.status_code == 200
    assert options.json()["allow_password_login"] is True
    assert options.json()["allow_sso_login"] is True
    assert options.json()["enforce_sso"] is False
    assert options.json()["active_sso_provider_count"] == 0
    assert options.json()["sso_available"] is False

    blocked = await client.patch(
        "/api/auth/organization/auth-settings",
        json={
            "allow_password_login": False,
            "allow_sso_login": True,
            "enforce_sso": True,
        },
        headers=sso_ctx["tenant_headers"],
    )
    assert blocked.status_code == 422
    assert blocked.json()["error"]["code"] == "SSO_PROVIDER_REQUIRED"

    await _create_provider(client, sso_ctx["tenant_headers"], name="Policy SSO")

    updated = await client.patch(
        "/api/auth/organization/auth-settings",
        json={
            "allow_password_login": False,
            "allow_sso_login": True,
            "enforce_sso": True,
        },
        headers=sso_ctx["tenant_headers"],
    )
    assert updated.status_code == 200
    assert updated.json()["enforce_sso"] is True
    assert updated.json()["active_sso_provider_count"] == 1
    assert updated.json()["sso_available"] is True

    options_after = await client.get(
        "/api/auth/login-options",
        params={"organization_id": sso_ctx["org_id"]},
    )
    assert options_after.status_code == 200
    assert options_after.json()["allow_password_login"] is False
    assert options_after.json()["enforce_sso"] is True


@pytest.mark.asyncio
async def test_password_login_blocked_when_org_enforces_sso(client: AsyncClient, sso_ctx: dict):
    await _create_provider(client, sso_ctx["tenant_headers"], name="Mandatory SSO")
    member = await _invite_and_accept(
        client,
        admin_headers=sso_ctx["tenant_headers"],
        email="member+sso@test.com",
        role="collector",
        full_name="SSO Member",
    )

    updated = await client.patch(
        "/api/auth/organization/auth-settings",
        json={
            "allow_password_login": False,
            "allow_sso_login": True,
            "enforce_sso": True,
        },
        headers=sso_ctx["tenant_headers"],
    )
    assert updated.status_code == 200

    blocked = await client.post(
        "/api/auth/login",
        json={"email": "member+sso@test.com", "password": "password123"},
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "SSO_REQUIRED"

    still_allowed = await client.get("/api/auth/me", headers=member["headers"])
    assert still_allowed.status_code == 200


@pytest.mark.asyncio
async def test_sso_service_rejects_non_editable_provider_fields(client: AsyncClient, sso_ctx: dict):
    provider_id = await _create_provider(client, sso_ctx["tenant_headers"], name="Unsafe Update SSO")
    me = await client.get("/api/auth/me", headers=sso_ctx["tenant_headers"])
    assert me.status_code == 200

    class UnsafePayload:
        def model_dump(self, mode: str = "json", exclude_unset: bool = True):
            return {"organization_id": sso_ctx["org_id"] + 1, "name": "Updated"}

    async with TestSessionLocal() as session:
        service = SSOService(
            sso_repo=SSORepository(session),
            user_repo=UserRepository(session),
            role_binding_repo=RoleBindingRepository(session),
            refresh_token_repo=RefreshTokenRepository(session),
            audit_repo=AuditRepository(session),
        )
        ctx = RequestContext(
            user_id=me.json()["id"],
            email=me.json()["email"],
            organization_id=sso_ctx["org_id"],
            role="admin",
        )
        with pytest.raises(AppError) as exc_info:
            await service.update_provider(provider_id, UnsafePayload(), ctx)

    assert exc_info.value.code == "SSO_PROVIDER_FIELD_NOT_EDITABLE"


@pytest.mark.asyncio
async def test_sso_start_blocked_when_org_disables_sso_login(client: AsyncClient, sso_ctx: dict):
    provider_id = await _create_provider(client, sso_ctx["tenant_headers"], name="Disabled SSO")

    disabled = await client.patch(
        "/api/auth/organization/auth-settings",
        json={"allow_sso_login": False},
        headers=sso_ctx["tenant_headers"],
    )
    assert disabled.status_code == 200
    assert disabled.json()["allow_sso_login"] is False

    started = await client.post(
        f"/api/auth/sso/providers/{provider_id}/start",
        json={"organization_id": sso_ctx["org_id"]},
    )
    assert started.status_code == 403
    assert started.json()["error"]["code"] == "SSO_DISABLED"
