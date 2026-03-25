from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes._auth_helpers import (
    resolve_client_ip,
    resolve_user_agent,
    serialize_auth_response,
)
from app.core.auth_cookies import (
    REFRESH_TOKEN_COOKIE_NAME,
    clear_access_token_cookie,
    clear_csrf_token_cookie,
    clear_current_organization_cookie,
    clear_refresh_token_cookie,
    clear_support_session_cookie,
    generate_csrf_token,
    set_access_token_cookie,
    set_csrf_token_cookie,
    set_current_organization_cookie,
    set_refresh_token_cookie,
)
from app.core.config import settings
from app.core.dependencies import (
    CurrentUser,
    RequestContext,
    get_current_context,
    get_current_user,
)
from app.core.exceptions import AppError
from app.db.models.organization import Organization
from app.db.models.role_binding import RoleBinding
from app.db.session import get_session
from app.policies.auth_policy import AuthPolicy
from app.repositories.audit_repo import AuditRepository
from app.repositories.refresh_token_repo import RefreshTokenRepository
from app.repositories.role_binding_repo import RoleBindingRepository
from app.repositories.user_repo import UserRepository
from app.schemas.auth import (
    AuthSessionListOut,
    AuthSessionRevokeOut,
    ChangePasswordRequest,
    InvitationCreateRequest,
    LoginRequest,
    LogoutAllOut,
    OrganizationAuthSettingsOut,
    OrganizationAuthSettingsUpdate,
    OrganizationSettingsOut,
    OrganizationSettingsUpdate,
    OrganizationUsersOut,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    TwoFactorDisableRequest,
    TwoFactorEnableRequest,
    TwoFactorSetupOut,
    TwoFactorStatusOut,
    UserProfileUpdateRequest,
    UserResponse,
    UserRoleUpdateRequest,
    UserStatusUpdateRequest,
)
from app.services.auth_service import AuthService
from app.services.invitation_service import InvitationService
from app.services.organization_user_service import OrganizationUserService

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class OrganizationContextUpdateRequest(BaseModel):
    organization_id: int | None = None


def _get_auth_service(session: AsyncSession) -> AuthService:
    return AuthService(
        user_repo=UserRepository(session),
        role_binding_repo=RoleBindingRepository(session),
        refresh_token_repo=RefreshTokenRepository(session),
        audit_repo=AuditRepository(session),
    )


def _get_organization_user_service(session: AsyncSession) -> OrganizationUserService:
    return OrganizationUserService(
        user_repo=UserRepository(session),
        role_binding_repo=RoleBindingRepository(session),
        refresh_token_repo=RefreshTokenRepository(session),
        invitation_service=InvitationService(session),
        audit_repo=AuditRepository(session),
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, session: AsyncSession = Depends(get_session)):
    if not settings.self_registration_enabled:
        raise AppError("REGISTRATION_DISABLED", 403, "Self-registration is currently disabled")
    service = _get_auth_service(session)
    return await service.register(payload.email, payload.password, payload.full_name)


@router.post("/login", response_model=TokenResponse, response_model_exclude_none=True)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    service = _get_auth_service(session)
    tokens = await service.login(
        payload.email,
        payload.password,
        totp_code=payload.totp_code,
        backup_code=payload.backup_code,
        request_id=getattr(request.state, "request_id", None),
        client_ip=resolve_client_ip(request),
        user_agent=resolve_user_agent(request),
    )
    set_access_token_cookie(response, tokens.access_token)
    set_csrf_token_cookie(response, generate_csrf_token())
    if tokens.refresh_token:
        set_refresh_token_cookie(response, tokens.refresh_token)
    return serialize_auth_response(request, tokens)


@router.get("/login-options", response_model=OrganizationAuthSettingsOut)
async def get_login_options(organization_id: int, session: AsyncSession = Depends(get_session)):
    return await _get_auth_service(session).get_login_options(organization_id)


@router.post("/refresh", response_model=TokenResponse, response_model_exclude_none=True)
async def refresh(
    request: Request,
    response: Response,
    payload: RefreshRequest | None = None,
    refresh_token_cookie: str | None = Cookie(default=None, alias=REFRESH_TOKEN_COOKIE_NAME),
    session: AsyncSession = Depends(get_session),
):
    service = _get_auth_service(session)
    refresh_token = refresh_token_cookie or (payload.refresh_token if payload else None)
    if not refresh_token:
        raise AppError("UNAUTHORIZED", 401, "Refresh token is required")
    tokens = await service.refresh(
        refresh_token,
        request_id=getattr(request.state, "request_id", None),
        client_ip=resolve_client_ip(request),
        user_agent=resolve_user_agent(request),
    )
    set_access_token_cookie(response, tokens.access_token)
    set_csrf_token_cookie(response, generate_csrf_token())
    if tokens.refresh_token:
        set_refresh_token_cookie(response, tokens.refresh_token)
    return serialize_auth_response(request, tokens)


@router.get("/me", response_model=UserResponse)
async def me(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    service = _get_auth_service(session)
    return await service.get_me(user.id)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    payload: UserProfileUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _get_auth_service(session).update_me(
        user.id,
        payload.model_dump(exclude_unset=True),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    user: CurrentUser = Depends(get_current_user),
    refresh_token_cookie: str | None = Cookie(default=None, alias=REFRESH_TOKEN_COOKIE_NAME),
    session: AsyncSession = Depends(get_session),
):
    service = _get_auth_service(session)
    await service.logout(
        user.id,
        current_refresh_token=refresh_token_cookie,
        request_id=getattr(request.state, "request_id", None),
    )
    clear_current_organization_cookie(response)
    clear_support_session_cookie(response)
    clear_access_token_cookie(response)
    clear_csrf_token_cookie(response)
    clear_refresh_token_cookie(response)


@router.post("/logout-all", response_model=LogoutAllOut)
async def logout_all(
    request: Request,
    response: Response,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await _get_auth_service(session).logout_all(
        user.id,
        request_id=getattr(request.state, "request_id", None),
    )
    clear_current_organization_cookie(response)
    clear_support_session_cookie(response)
    clear_access_token_cookie(response)
    clear_csrf_token_cookie(response)
    clear_refresh_token_cookie(response)
    return result


@router.post("/context/organization")
async def set_organization_context(
    payload: OrganizationContextUpdateRequest,
    response: Response,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if payload.organization_id is None:
        clear_current_organization_cookie(response)
        return {"organization_id": None, "cleared": True}

    org_result = await session.execute(
        select(Organization.id).where(Organization.id == payload.organization_id)
    )
    organization_id = org_result.scalar_one_or_none()
    if organization_id is None:
        raise AppError("NOT_FOUND", 404, f"Organization {payload.organization_id} not found")

    platform_binding = await session.execute(
        select(RoleBinding.id).where(
            RoleBinding.user_id == user.id,
            RoleBinding.scope_type == "platform",
            RoleBinding.role == "platform_admin",
        )
    )
    if platform_binding.scalar_one_or_none() is None:
        binding_result = await session.execute(
            select(RoleBinding.id).where(
                RoleBinding.user_id == user.id,
                RoleBinding.scope_type == "organization",
                RoleBinding.scope_id == payload.organization_id,
            )
        )
        if binding_result.scalar_one_or_none() is None:
            raise AppError("FORBIDDEN", 403, "No access to this organization")

    set_current_organization_cookie(response, payload.organization_id)
    return {"organization_id": payload.organization_id, "cleared": False}


@router.post("/change-password")
async def change_password(
    request: Request,
    response: Response,
    payload: ChangePasswordRequest,
    user: CurrentUser = Depends(get_current_user),
    refresh_token_cookie: str | None = Cookie(default=None, alias=REFRESH_TOKEN_COOKIE_NAME),
    session: AsyncSession = Depends(get_session),
):
    result = await _get_auth_service(session).change_password(
        user.id,
        current_password=payload.current_password,
        new_password=payload.new_password,
        current_refresh_token=refresh_token_cookie,
        request_id=getattr(request.state, "request_id", None),
    )
    if not result.get("current_session_preserved", False):
        clear_access_token_cookie(response)
        clear_csrf_token_cookie(response)
        clear_refresh_token_cookie(response)
    return result


@router.get("/sessions", response_model=AuthSessionListOut)
async def list_sessions(
    user: CurrentUser = Depends(get_current_user),
    refresh_token_cookie: str | None = Cookie(default=None, alias=REFRESH_TOKEN_COOKIE_NAME),
    session: AsyncSession = Depends(get_session),
):
    return await _get_auth_service(session).list_sessions(
        user.id,
        current_refresh_token=refresh_token_cookie,
    )


@router.delete("/sessions/{session_id}", response_model=AuthSessionRevokeOut)
async def revoke_session(
    session_id: int,
    request: Request,
    response: Response,
    user: CurrentUser = Depends(get_current_user),
    refresh_token_cookie: str | None = Cookie(default=None, alias=REFRESH_TOKEN_COOKIE_NAME),
    session: AsyncSession = Depends(get_session),
):
    result = await _get_auth_service(session).revoke_session(
        user.id,
        session_id,
        current_refresh_token=refresh_token_cookie,
        request_id=getattr(request.state, "request_id", None),
    )
    if result.is_current:
        clear_access_token_cookie(response)
        clear_csrf_token_cookie(response)
        clear_refresh_token_cookie(response)
    return result


@router.get("/me/organization", response_model=OrganizationSettingsOut)
async def get_my_organization_settings(
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.require_role(ctx, ["admin", "platform_admin"])
    return await _get_auth_service(session).get_my_organization_settings(ctx)


@router.patch("/me/organization", response_model=OrganizationSettingsOut)
async def update_my_organization_settings(
    payload: OrganizationSettingsUpdate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.require_role(ctx, ["admin", "platform_admin"])
    return await _get_auth_service(session).update_my_organization_settings(
        ctx,
        payload.model_dump(exclude_unset=True),
    )


@router.get("/2fa/status", response_model=TwoFactorStatusOut)
async def get_two_factor_status(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _get_auth_service(session).get_two_factor_status(user.id)


@router.post("/2fa/setup", response_model=TwoFactorSetupOut)
async def setup_two_factor(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _get_auth_service(session).setup_two_factor(user.id)


@router.post("/2fa/enable", response_model=TwoFactorStatusOut)
async def enable_two_factor(
    payload: TwoFactorEnableRequest,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _get_auth_service(session).enable_two_factor(user.id, payload.code)


@router.post("/2fa/disable", response_model=TwoFactorStatusOut)
async def disable_two_factor(
    payload: TwoFactorDisableRequest,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _get_auth_service(session).disable_two_factor(
        user.id,
        code=payload.code,
        backup_code=payload.backup_code,
    )


@router.get("/organization/users", response_model=OrganizationUsersOut)
async def list_organization_users(
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_organization_user_service(session).list_organization_users(ctx)


@router.get("/organization/auth-settings", response_model=OrganizationAuthSettingsOut)
async def get_organization_auth_settings(
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.require_manager_or_admin(ctx)
    return await _get_auth_service(session).get_organization_auth_settings(ctx)


@router.patch("/organization/auth-settings", response_model=OrganizationAuthSettingsOut)
async def update_organization_auth_settings(
    payload: OrganizationAuthSettingsUpdate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.require_manager_or_admin(ctx)
    return await _get_auth_service(session).update_organization_auth_settings(payload, ctx)


@router.post("/invitations", status_code=status.HTTP_201_CREATED)
async def create_auth_invitation(
    payload: InvitationCreateRequest,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.require_role(ctx, ["admin", "platform_admin"])
    return await InvitationService(session).create_invitation(
        org_id=ctx.organization_id,
        email=payload.email,
        role=payload.role,
        invited_by=ctx.user_id,
    )


@router.post("/invitations/{invitation_id}/resend")
async def resend_auth_invitation(
    invitation_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.require_role(ctx, ["admin", "platform_admin"])
    return await InvitationService(session).resend_invitation(
        invitation_id=invitation_id,
        org_id=ctx.organization_id,
        invited_by=ctx.user_id,
    )


@router.delete("/invitations/{invitation_id}")
async def cancel_auth_invitation(
    invitation_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.require_role(ctx, ["admin", "platform_admin"])
    return await InvitationService(session).cancel_invitation(
        invitation_id=invitation_id,
        org_id=ctx.organization_id,
    )


@router.patch("/users/{user_id}/role")
async def update_organization_user_role(
    user_id: int,
    payload: UserRoleUpdateRequest,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_organization_user_service(session).update_user_role(
        user_id,
        payload.role,
        ctx,
    )


@router.patch("/users/{user_id}/status")
async def update_organization_user_status(
    user_id: int,
    payload: UserStatusUpdateRequest,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_organization_user_service(session).update_user_status(
        user_id,
        payload.status,
        ctx,
    )


@router.delete("/users/{user_id}")
async def remove_organization_user(
    user_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_organization_user_service(session).remove_user_from_organization(user_id, ctx)
