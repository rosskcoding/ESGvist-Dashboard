from datetime import UTC, datetime

from fastapi import Cookie, Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_cookies import (
    ACCESS_TOKEN_COOKIE_NAME,
    CURRENT_ORGANIZATION_COOKIE_NAME,
    SUPPORT_SESSION_COOKIE_NAME,
)
from app.core.exceptions import AppError
from app.core.security import decode_token
from app.db.models.organization import Organization
from app.db.models.refresh_token import RefreshToken
from app.db.models.role_binding import RoleBinding
from app.db.models.user import User
from app.db.session import get_session

security_scheme = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    id: int
    email: str
    session_id: int | None = None


class RequestContext(BaseModel):
    user_id: int
    email: str
    organization_id: int | None = None
    role: str | None = None
    is_platform_admin: bool = False
    support_mode: bool = False
    support_session_id: int | None = None


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    access_token_cookie: str | None = Cookie(default=None, alias=ACCESS_TOKEN_COOKIE_NAME),
    session: AsyncSession = Depends(get_session),
) -> CurrentUser:
    raw_token = credentials.credentials if credentials else access_token_cookie
    if not raw_token:
        raise AppError(code="UNAUTHORIZED", status_code=401, message="Not authenticated")
    payload = decode_token(raw_token)
    if payload.token_type != "access":
        raise AppError(code="UNAUTHORIZED", status_code=401, message="Invalid token type")
    if payload.sid is not None:
        refresh_session_result = await session.execute(
            select(RefreshToken).where(
                RefreshToken.id == payload.sid,
                RefreshToken.user_id == payload.sub,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > datetime.now(UTC),
            )
        )
        refresh_session = refresh_session_result.scalar_one_or_none()
        if not refresh_session:
            raise AppError(
                code="UNAUTHORIZED",
                status_code=401,
                message="Session is revoked or expired",
            )
    result = await session.execute(select(User).where(User.id == payload.sub))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise AppError(code="FORBIDDEN", status_code=403, message="Account is deactivated")
    request.state.user_id = user.id
    return CurrentUser(id=payload.sub, email=payload.email, session_id=payload.sid)


async def get_current_context(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    x_organization_id: int | None = Header(None, alias="X-Organization-Id"),
    x_support_session_id: int | None = Header(None, alias="X-Support-Session-Id"),
    organization_id_cookie: str | None = Cookie(
        default=None,
        alias=CURRENT_ORGANIZATION_COOKIE_NAME,
    ),
    support_session_cookie: str | None = Cookie(
        default=None,
        alias=SUPPORT_SESSION_COOKIE_NAME,
    ),
    session: AsyncSession = Depends(get_session),
) -> RequestContext:
    # Check platform_admin
    result = await session.execute(
        select(RoleBinding).where(
            RoleBinding.user_id == user.id,
            RoleBinding.scope_type == "platform",
            RoleBinding.role == "platform_admin",
        )
    )
    is_platform_admin = result.scalar_one_or_none() is not None
    resolved_organization_id = x_organization_id
    if resolved_organization_id is None and organization_id_cookie:
        try:
            resolved_organization_id = int(organization_id_cookie)
        except ValueError as exc:
            raise AppError(
                "INVALID_ORGANIZATION_CONTEXT",
                400,
                "Current organization cookie is invalid",
            ) from exc

    resolved_support_session_id = x_support_session_id
    if resolved_support_session_id is None and support_session_cookie:
        try:
            resolved_support_session_id = int(support_session_cookie)
        except ValueError as exc:
            raise AppError(
                "INVALID_SUPPORT_SESSION",
                400,
                "Support session cookie is invalid",
            ) from exc

    # Support mode: platform admin acting within a tenant
    if resolved_support_session_id and not is_platform_admin:
        raise AppError(
            "PLATFORM_ADMIN_REQUIRED",
            403,
            "Platform admin access required for support sessions",
        )

    if resolved_support_session_id and is_platform_admin:
        from app.db.models.support_session import SupportSession

        ss_result = await session.execute(
            select(SupportSession).where(
                SupportSession.id == resolved_support_session_id,
                SupportSession.platform_admin_id == user.id,
                SupportSession.is_active == True,  # noqa: E712
            )
        )
        support_session = ss_result.scalar_one_or_none()
        if not support_session:
            raise AppError(
                "NOT_FOUND",
                404,
                f"Support session {resolved_support_session_id} not found",
            )
        if (
            resolved_organization_id is not None
            and resolved_organization_id != support_session.tenant_id
        ):
            raise AppError(
                "SUPPORT_SESSION_ORG_MISMATCH",
                409,
                "Support session tenant does not match X-Organization-Id",
            )

        request.state.user_id = user.id
        request.state.organization_id = support_session.tenant_id
        request.state.role = "platform_admin"
        return RequestContext(
            user_id=user.id,
            email=user.email,
            organization_id=support_session.tenant_id,
            role="platform_admin",
            is_platform_admin=True,
            support_mode=True,
            support_session_id=support_session.id,
        )

    # Platform endpoints — no org needed
    if is_platform_admin and resolved_organization_id is None:
        request.state.user_id = user.id
        request.state.role = "platform_admin"
        return RequestContext(
            user_id=user.id,
            email=user.email,
            organization_id=None,
            role="platform_admin",
            is_platform_admin=True,
        )

    # Tenant endpoints — org header required
    if resolved_organization_id is None:
        raise AppError(
            code="ORG_HEADER_REQUIRED",
            status_code=400,
            message="X-Organization-Id header is required for tenant endpoints",
        )

    # Resolve tenant role
    result = await session.execute(
        select(RoleBinding).where(
            RoleBinding.user_id == user.id,
            RoleBinding.scope_type == "organization",
            RoleBinding.scope_id == resolved_organization_id,
        )
    )
    binding = result.scalar_one_or_none()

    if binding is None and not is_platform_admin:
        raise AppError(code="FORBIDDEN", status_code=403, message="No access to this organization")

    org_result = await session.execute(
        select(Organization).where(Organization.id == resolved_organization_id)
    )
    organization = org_result.scalar_one_or_none()
    if not organization:
        raise AppError("NOT_FOUND", 404, f"Organization {resolved_organization_id} not found")
    if not is_platform_admin:
        if organization.status == "suspended":
            raise AppError("TENANT_SUSPENDED", 403, "Tenant is suspended")
        if organization.status == "archived":
            raise AppError("TENANT_ARCHIVED", 403, "Tenant is archived")

    request.state.user_id = user.id
    request.state.organization_id = resolved_organization_id
    request.state.role = binding.role if binding else "platform_admin"
    return RequestContext(
        user_id=user.id,
        email=user.email,
        organization_id=resolved_organization_id,
        role=binding.role if binding else "platform_admin",
        is_platform_admin=is_platform_admin,
    )


async def get_current_onboarding_context(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RequestContext:
    result = await session.execute(
        select(RoleBinding).where(
            RoleBinding.user_id == user.id,
            RoleBinding.scope_type == "platform",
            RoleBinding.role == "platform_admin",
        )
    )
    is_platform_admin = result.scalar_one_or_none() is not None

    request.state.user_id = user.id
    request.state.organization_id = None
    request.state.role = "platform_admin" if is_platform_admin else None

    return RequestContext(
        user_id=user.id,
        email=user.email,
        organization_id=None,
        role="platform_admin" if is_platform_admin else None,
        is_platform_admin=is_platform_admin,
    )
