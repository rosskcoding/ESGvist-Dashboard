from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import CurrentUser, RequestContext, get_current_context, get_current_user
from app.core.exceptions import AppError
from app.db.session import get_session
from app.policies.auth_policy import AuthPolicy
from app.repositories.audit_repo import AuditRepository
from app.repositories.refresh_token_repo import RefreshTokenRepository
from app.repositories.role_binding_repo import RoleBindingRepository
from app.repositories.user_repo import UserRepository
from app.schemas.auth import (
    InvitationCreateRequest,
    LoginRequest,
    OrganizationAuthSettingsOut,
    OrganizationAuthSettingsUpdate,
    OrganizationUsersOut,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserRoleUpdateRequest,
    UserStatusUpdateRequest,
    UserResponse,
)
from app.services.auth_service import AuthService
from app.services.invitation_service import InvitationService
from app.services.organization_user_service import OrganizationUserService

router = APIRouter(prefix="/api/auth", tags=["Auth"])


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
    if not settings.allow_self_registration:
        raise AppError("REGISTRATION_DISABLED", 403, "Self-registration is currently disabled")
    service = _get_auth_service(session)
    return await service.register(payload.email, payload.password, payload.full_name)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_session)):
    service = _get_auth_service(session)
    return await service.login(payload.email, payload.password)


@router.get("/login-options", response_model=OrganizationAuthSettingsOut)
async def get_login_options(organization_id: int, session: AsyncSession = Depends(get_session)):
    return await _get_auth_service(session).get_login_options(organization_id)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, session: AsyncSession = Depends(get_session)):
    service = _get_auth_service(session)
    return await service.refresh(payload.refresh_token)


@router.get("/me", response_model=UserResponse)
async def me(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    service = _get_auth_service(session)
    return await service.get_me(user.id)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    service = _get_auth_service(session)
    await service.logout(user.id)


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
    AuthPolicy.require_manager_or_admin(ctx)
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
    AuthPolicy.require_manager_or_admin(ctx)
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
    AuthPolicy.require_manager_or_admin(ctx)
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
    return await _get_organization_user_service(session).update_user_role(user_id, payload.role, ctx)


@router.patch("/users/{user_id}/status")
async def update_organization_user_status(
    user_id: int,
    payload: UserStatusUpdateRequest,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_organization_user_service(session).update_user_status(user_id, payload.status, ctx)


@router.delete("/users/{user_id}")
async def remove_organization_user(
    user_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_organization_user_service(session).remove_user_from_organization(user_id, ctx)
