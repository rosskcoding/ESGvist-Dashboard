from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.security import decode_token
from app.db.models.organization import Organization
from app.db.models.role_binding import RoleBinding
from app.db.models.user import User
from app.db.session import get_session

security_scheme = HTTPBearer()


class CurrentUser(BaseModel):
    id: int
    email: str


class RequestContext(BaseModel):
    user_id: int
    email: str
    organization_id: int | None = None
    role: str | None = None
    is_platform_admin: bool = False


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    session: AsyncSession = Depends(get_session),
) -> CurrentUser:
    payload = decode_token(credentials.credentials)
    if payload.token_type != "access":
        raise AppError(code="UNAUTHORIZED", status_code=401, message="Invalid token type")
    result = await session.execute(select(User).where(User.id == payload.sub))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise AppError(code="FORBIDDEN", status_code=403, message="Account is deactivated")
    request.state.user_id = user.id
    return CurrentUser(id=payload.sub, email=payload.email)


async def get_current_context(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    x_organization_id: int | None = Header(None, alias="X-Organization-Id"),
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

    # Platform endpoints — no org needed
    if is_platform_admin and x_organization_id is None:
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
    if x_organization_id is None:
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
            RoleBinding.scope_id == x_organization_id,
        )
    )
    binding = result.scalar_one_or_none()

    if binding is None and not is_platform_admin:
        raise AppError(
            code="FORBIDDEN", status_code=403, message="No access to this organization"
        )

    org_result = await session.execute(
        select(Organization).where(Organization.id == x_organization_id)
    )
    organization = org_result.scalar_one_or_none()
    if not organization:
        if is_platform_admin and binding is None:
            request.state.user_id = user.id
            request.state.role = "platform_admin"
            return RequestContext(
                user_id=user.id,
                email=user.email,
                organization_id=None,
                role="platform_admin",
                is_platform_admin=True,
            )
        raise AppError("NOT_FOUND", 404, f"Organization {x_organization_id} not found")
    if not is_platform_admin:
        if organization.status == "suspended":
            raise AppError("TENANT_SUSPENDED", 403, "Tenant is suspended")
        if organization.status == "archived":
            raise AppError("TENANT_ARCHIVED", 403, "Tenant is archived")

    request.state.user_id = user.id
    request.state.organization_id = x_organization_id
    request.state.role = binding.role if binding else "platform_admin"
    return RequestContext(
        user_id=user.id,
        email=user.email,
        organization_id=x_organization_id,
        role=binding.role if binding else "platform_admin",
        is_platform_admin=is_platform_admin,
    )
