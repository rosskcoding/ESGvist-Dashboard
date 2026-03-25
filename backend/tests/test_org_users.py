import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.db.models.invitation import UserInvitation
from app.repositories.audit_repo import AuditRepository
from app.repositories.refresh_token_repo import RefreshTokenRepository
from app.repositories.role_binding_repo import RoleBindingRepository
from app.repositories.user_repo import UserRepository
from app.services.invitation_service import InvitationService
from app.services.organization_user_service import OrganizationUserService
from tests.conftest import TestSessionLocal


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
    admin_row = next(user for user in data["users"] if user["email"] == "admin@org.com")
    assert admin_row["roles"] == ["admin"]
    assert any(
        user["email"] == "reviewer@org.com" and user["role"] == "reviewer"
        for user in data["users"]
    )
    reviewer_row = next(user for user in data["users"] if user["email"] == "reviewer@org.com")
    assert reviewer_row["roles"] == ["reviewer"]
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

    me_still_works = await client.get("/api/auth/me", headers=collector["headers"])
    assert me_still_works.status_code == 200

    blocked_org_access = await client.get("/api/projects", headers=collector["headers"])
    assert blocked_org_access.status_code == 403

    reinvite = await client.post(
        "/api/auth/invitations",
        json={"email": "collector@org.com", "role": "reviewer"},
        headers=org["headers"],
    )
    assert reinvite.status_code == 201

    reaccept = await client.post(
        f"/api/invitations/accept/{reinvite.json()['token']}",
        headers=collector["headers"],
    )
    assert reaccept.status_code == 200
    assert reaccept.json()["accepted"] is True

    restored_org_access = await client.get("/api/projects", headers=collector["headers"])
    assert restored_org_access.status_code == 200

    remove = await client.delete(
        f"/api/auth/users/{collector['user_id']}",
        headers=org["headers"],
    )
    assert remove.status_code == 200
    assert remove.json()["removed"] is True

    no_org_access = await client.get("/api/projects", headers=collector["headers"])
    assert no_org_access.status_code == 403


@pytest.mark.asyncio
async def test_organization_user_service_rejects_invalid_status_value(client: AsyncClient):
    org = await _setup_org_admin(client)
    collector = await _invite_and_accept(
        client,
        org["headers"],
        email="collector-invalid-status@org.com",
        role="collector",
        full_name="Collector Invalid Status",
    )
    me = await client.get("/api/auth/me", headers=org["headers"])
    assert me.status_code == 200

    async with TestSessionLocal() as session:
        service = OrganizationUserService(
            user_repo=UserRepository(session),
            role_binding_repo=RoleBindingRepository(session),
            refresh_token_repo=RefreshTokenRepository(session),
            invitation_service=InvitationService(session),
            audit_repo=AuditRepository(session),
        )
        ctx = RequestContext(
            user_id=me.json()["id"],
            email=me.json()["email"],
            organization_id=org["org_id"],
            role="admin",
        )

        with pytest.raises(AppError) as exc_info:
            await service.update_user_status(collector["user_id"], "disabled", ctx)

    assert exc_info.value.code == "INVALID_STATUS"


@pytest.mark.asyncio
async def test_esg_manager_can_manage_non_admin_users_but_not_admins(client: AsyncClient):
    org = await _setup_org_admin(client)
    manager = await _invite_and_accept(
        client,
        org["headers"],
        email="manager@org.com",
        role="esg_manager",
        full_name="ESG Manager",
    )
    collector = await _invite_and_accept(
        client,
        org["headers"],
        email="collector-managed@org.com",
        role="collector",
        full_name="Managed Collector",
    )

    listed = await client.get("/api/auth/organization/users", headers=manager["headers"])
    assert listed.status_code == 200
    assert any(user["email"] == "collector-managed@org.com" for user in listed.json()["users"])

    updated = await client.patch(
        f"/api/auth/users/{collector['user_id']}/role",
        json={"role": "reviewer"},
        headers=manager["headers"],
    )
    assert updated.status_code == 200
    assert updated.json()["role"] == "reviewer"

    promote_admin = await client.patch(
        f"/api/auth/users/{collector['user_id']}/role",
        json={"role": "admin"},
        headers=manager["headers"],
    )
    assert promote_admin.status_code == 403
    assert promote_admin.json()["error"]["code"] == "FORBIDDEN"

    admin_me = await client.get("/api/auth/me", headers=org["headers"])
    assert admin_me.status_code == 200
    demote_admin = await client.patch(
        f"/api/auth/users/{admin_me.json()['id']}/role",
        json={"role": "reviewer"},
        headers=manager["headers"],
    )
    assert demote_admin.status_code == 403
    assert demote_admin.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_create_invitation_rejects_existing_org_member(client: AsyncClient):
    org = await _setup_org_admin(client)
    await _invite_and_accept(
        client,
        org["headers"],
        email="existing-member@org.com",
        role="collector",
        full_name="Existing Member",
    )

    duplicate = await client.post(
        "/api/auth/invitations",
        json={"email": "existing-member@org.com", "role": "reviewer"},
        headers=org["headers"],
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "INVITATION_MEMBER_EXISTS"


@pytest.mark.asyncio
async def test_pending_invitation_unique_index_blocks_duplicate_pending_rows(client: AsyncClient):
    org = await _setup_org_admin(client)
    me = await client.get("/api/auth/me", headers=org["headers"])
    assert me.status_code == 200

    async with TestSessionLocal() as session:
        service = InvitationService(session)
        await service.create_invitation(
            org_id=org["org_id"],
            email="duplicate-pending@org.com",
            role="collector",
            invited_by=me.json()["id"],
        )
        await session.commit()

    async with TestSessionLocal() as session:
        session.add(
            UserInvitation(
                organization_id=org["org_id"],
                email="duplicate-pending@org.com",
                role="reviewer",
                invited_by=me.json()["id"],
                token=str(uuid.uuid4()),
                expires_at=datetime.now(UTC) + timedelta(days=7),
                status="pending",
            )
        )
        with pytest.raises(IntegrityError):
            await session.flush()


@pytest.mark.asyncio
async def test_create_invitation_maps_unique_race_to_invitation_exists(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    org = await _setup_org_admin(client)
    me = await client.get("/api/auth/me", headers=org["headers"])
    assert me.status_code == 200

    async with TestSessionLocal() as session:
        service = InvitationService(session)

        async def _flush_conflict() -> None:
            raise IntegrityError("insert", {"email": "race@org.com"}, Exception("duplicate"))

        monkeypatch.setattr(session, "flush", _flush_conflict)

        with pytest.raises(AppError) as exc_info:
            await service.create_invitation(
                org_id=org["org_id"],
                email="race@org.com",
                role="collector",
                invited_by=me.json()["id"],
            )

    assert exc_info.value.code == "INVITATION_EXISTS"


@pytest.mark.asyncio
async def test_get_invitation_info_does_not_mutate_expired_invitation(client: AsyncClient):
    org = await _setup_org_admin(client)
    me = await client.get("/api/auth/me", headers=org["headers"])
    assert me.status_code == 200

    async with TestSessionLocal() as session:
        service = InvitationService(session)
        created = await service.create_invitation(
            org_id=org["org_id"],
            email="expired-preview@org.com",
            role="collector",
            invited_by=me.json()["id"],
            expires_days=-1,
        )
        await session.commit()

    preview = await client.get(f"/api/invitations/accept?token={created['token']}")
    assert preview.status_code == 410
    assert preview.json()["error"]["code"] == "INVITATION_EXPIRED"

    async with TestSessionLocal() as session:
        invitation = (
            await session.execute(
                select(UserInvitation).where(UserInvitation.token == created["token"])
            )
        ).scalar_one()
    assert invitation.status == "pending"


@pytest.mark.asyncio
async def test_accept_invitation_returns_specific_error_for_already_accepted(client: AsyncClient):
    org = await _setup_org_admin(client)
    invitation = await client.post(
        "/api/auth/invitations",
        json={"email": "accepted@org.com", "role": "collector"},
        headers=org["headers"],
    )
    assert invitation.status_code == 201

    await client.post(
        "/api/auth/register",
        json={"email": "accepted@org.com", "password": "password123", "full_name": "Accepted User"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": "accepted@org.com", "password": "password123"},
    )
    user_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    first = await client.post(
        f"/api/invitations/accept/{invitation.json()['token']}",
        headers=user_headers,
    )
    assert first.status_code == 200

    second = await client.post(
        f"/api/invitations/accept/{invitation.json()['token']}",
        headers=user_headers,
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "INVITATION_ALREADY_ACCEPTED"


@pytest.mark.asyncio
async def test_accept_invitation_returns_specific_error_for_declined_invitation(
    client: AsyncClient,
):
    org = await _setup_org_admin(client)
    invitation = await client.post(
        "/api/auth/invitations",
        json={"email": "declined@org.com", "role": "collector"},
        headers=org["headers"],
    )
    assert invitation.status_code == 201

    await client.post(
        "/api/auth/register",
        json={"email": "declined@org.com", "password": "password123", "full_name": "Declined User"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": "declined@org.com", "password": "password123"},
    )
    user_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    async with TestSessionLocal() as session:
        service = InvitationService(session)
        declined = await service.decline_invitation(invitation.json()["token"])
        await session.commit()
    assert declined["declined"] is True

    accept = await client.post(
        f"/api/invitations/accept/{invitation.json()['token']}",
        headers=user_headers,
    )
    assert accept.status_code == 409
    assert accept.json()["error"]["code"] == "INVITATION_DECLINED"


@pytest.mark.asyncio
async def test_accept_invitation_returns_specific_error_for_expired_invitation(client: AsyncClient):
    org = await _setup_org_admin(client)
    me = await client.get("/api/auth/me", headers=org["headers"])
    assert me.status_code == 200

    async with TestSessionLocal() as session:
        service = InvitationService(session)
        created = await service.create_invitation(
            org_id=org["org_id"],
            email="expired-accept@org.com",
            role="collector",
            invited_by=me.json()["id"],
            expires_days=-1,
        )
        await session.commit()

    await client.post(
        "/api/auth/register",
        json={
            "email": "expired-accept@org.com",
            "password": "password123",
            "full_name": "Expired Accept User",
        },
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": "expired-accept@org.com", "password": "password123"},
    )
    user_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    accept = await client.post(f"/api/invitations/accept/{created['token']}", headers=user_headers)
    assert accept.status_code == 410
    assert accept.json()["error"]["code"] == "INVITATION_EXPIRED"


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
