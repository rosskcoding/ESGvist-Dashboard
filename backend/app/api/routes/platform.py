from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.core.exceptions import AppError
from app.db.models.organization import Organization
from app.db.models.role_binding import RoleBinding
from app.db.models.user import User
from app.db.session import get_session

router = APIRouter(prefix="/api/platform", tags=["Platform Admin"])


def _require_platform(ctx: RequestContext):
    if not ctx.is_platform_admin:
        raise AppError("PLATFORM_ADMIN_REQUIRED", 403, "Platform admin access required")


# --- Tenants ---
@router.get("/tenants")
async def list_tenants(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    _require_platform(ctx)

    count_q = select(func.count()).select_from(Organization)
    total = (await session.execute(count_q)).scalar_one()

    q = select(Organization).order_by(Organization.id).offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(q)
    orgs = result.scalars().all()

    items = []
    for org in orgs:
        user_count_q = select(func.count()).select_from(RoleBinding).where(
            RoleBinding.scope_type == "organization", RoleBinding.scope_id == org.id
        )
        user_count = (await session.execute(user_count_q)).scalar_one()
        items.append({
            "id": org.id,
            "name": org.name,
            "country": org.country,
            "industry": org.industry,
            "setup_completed": org.setup_completed,
            "user_count": user_count,
        })

    return {"items": items, "total": total}


@router.get("/tenants/{tenant_id}")
async def get_tenant(
    tenant_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    _require_platform(ctx)
    result = await session.execute(select(Organization).where(Organization.id == tenant_id))
    org = result.scalar_one_or_none()
    if not org:
        raise AppError("NOT_FOUND", 404, f"Tenant {tenant_id} not found")

    return {
        "id": org.id,
        "name": org.name,
        "country": org.country,
        "industry": org.industry,
        "default_currency": org.default_currency,
        "setup_completed": org.setup_completed,
    }


class TenantUpdate(BaseModel):
    name: str | None = None
    country: str | None = None
    industry: str | None = None


@router.patch("/tenants/{tenant_id}")
async def update_tenant(
    tenant_id: int,
    payload: TenantUpdate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    _require_platform(ctx)
    result = await session.execute(select(Organization).where(Organization.id == tenant_id))
    org = result.scalar_one_or_none()
    if not org:
        raise AppError("NOT_FOUND", 404, f"Tenant {tenant_id} not found")

    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(org, k, v)
    await session.flush()
    return {"id": org.id, "name": org.name, "updated": True}


@router.post("/tenants/{tenant_id}/suspend")
async def suspend_tenant(
    tenant_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    _require_platform(ctx)
    result = await session.execute(select(Organization).where(Organization.id == tenant_id))
    org = result.scalar_one_or_none()
    if not org:
        raise AppError("NOT_FOUND", 404, f"Tenant {tenant_id} not found")

    org.setup_completed = False  # Using as suspended flag for now
    await session.flush()
    return {"id": org.id, "status": "suspended"}


@router.post("/tenants/{tenant_id}/reactivate")
async def reactivate_tenant(
    tenant_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    _require_platform(ctx)
    result = await session.execute(select(Organization).where(Organization.id == tenant_id))
    org = result.scalar_one_or_none()
    if not org:
        raise AppError("NOT_FOUND", 404, f"Tenant {tenant_id} not found")

    org.setup_completed = True
    await session.flush()
    return {"id": org.id, "status": "active"}


# --- Platform Users ---
@router.get("/users")
async def list_platform_users(
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    _require_platform(ctx)
    result = await session.execute(select(User).order_by(User.id))
    users = result.scalars().all()
    return {
        "items": [
            {"id": u.id, "email": u.email, "full_name": u.full_name, "is_active": u.is_active}
            for u in users
        ]
    }


class AssignAdminRequest(BaseModel):
    user_id: int


@router.post("/tenants/{tenant_id}/admins")
async def assign_admin(
    tenant_id: int,
    payload: AssignAdminRequest,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    _require_platform(ctx)

    # Check user exists
    user = await session.execute(select(User).where(User.id == payload.user_id))
    if not user.scalar_one_or_none():
        raise AppError("NOT_FOUND", 404, f"User {payload.user_id} not found")

    # Check binding doesn't exist
    existing = await session.execute(
        select(RoleBinding).where(
            RoleBinding.user_id == payload.user_id,
            RoleBinding.scope_type == "organization",
            RoleBinding.scope_id == tenant_id,
        )
    )
    if existing.scalar_one_or_none():
        raise AppError("ROLE_BINDING_EXISTS", 409, "User already has a role in this organization")

    binding = RoleBinding(
        user_id=payload.user_id,
        role="admin",
        scope_type="organization",
        scope_id=tenant_id,
        created_by=ctx.user_id,
    )
    session.add(binding)
    await session.flush()
    return {"user_id": payload.user_id, "tenant_id": tenant_id, "role": "admin"}
