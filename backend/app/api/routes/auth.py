from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import CurrentUser, RequestContext, get_current_context, get_current_user
from app.core.exceptions import AppError
from app.db.session import get_session
from app.repositories.audit_repo import AuditRepository
from app.repositories.refresh_token_repo import RefreshTokenRepository
from app.repositories.role_binding_repo import RoleBindingRepository
from app.repositories.user_repo import UserRepository
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["Auth"])


def _get_auth_service(session: AsyncSession) -> AuthService:
    return AuthService(
        user_repo=UserRepository(session),
        role_binding_repo=RoleBindingRepository(session),
        refresh_token_repo=RefreshTokenRepository(session),
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


@router.get("/organization/users")
async def list_organization_users(
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    from sqlalchemy import select
    from app.db.models.role_binding import RoleBinding
    from app.db.models.user import User

    result = await session.execute(
        select(User, RoleBinding.role).join(
            RoleBinding, RoleBinding.user_id == User.id
        ).where(
            RoleBinding.scope_type == "organization",
            RoleBinding.scope_id == ctx.organization_id,
        )
    )
    users = [
        {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "role": role,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }
        for user, role in result.all()
    ]
    return users
