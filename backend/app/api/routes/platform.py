from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import RequestContext, get_current_context
from app.core.exceptions import AppError
from app.db.models.organization import Organization
from app.db.models.role_binding import RoleBinding
from app.db.models.user import User
from app.db.session import get_session
from app.repositories.audit_repo import AuditRepository
from app.repositories.notification_repo import NotificationRepository
from app.repositories.webhook_repo import WebhookRepository
from app.services.sla_service import SLAService
from app.services.webhook_service import WebhookService

router = APIRouter(prefix="/api/platform", tags=["Platform Admin"])


def _require_platform(ctx: RequestContext) -> None:
    if not ctx.is_platform_admin:
        raise AppError("PLATFORM_ADMIN_REQUIRED", 403, "Platform admin access required")


async def _get_tenant_or_raise(session: AsyncSession, tenant_id: int) -> Organization:
    result = await session.execute(select(Organization).where(Organization.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise AppError("NOT_FOUND", 404, f"Tenant {tenant_id} not found")
    return tenant


async def _audit_platform(
    session: AsyncSession,
    ctx: RequestContext,
    *,
    entity_type: str,
    action: str,
    entity_id: int | None = None,
    organization_id: int | None = None,
    changes: dict | None = None,
) -> None:
    await AuditRepository(session).log(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        user_id=ctx.user_id,
        organization_id=organization_id,
        changes=changes,
        performed_by_platform_admin=True,
    )


@router.get("/tenants")
async def list_tenants(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    _require_platform(ctx)

    total = (await session.execute(select(func.count()).select_from(Organization))).scalar_one()
    result = await session.execute(
        select(Organization)
        .order_by(Organization.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    organizations = result.scalars().all()

    items = []
    for org in organizations:
        user_count = (
            await session.execute(
                select(func.count()).select_from(RoleBinding).where(
                    RoleBinding.scope_type == "organization",
                    RoleBinding.scope_id == org.id,
                )
            )
        ).scalar_one()
        items.append(
            {
                "id": org.id,
                "name": org.name,
                "country": org.country,
                "industry": org.industry,
                "status": org.status,
                "setup_completed": org.setup_completed,
                "user_count": user_count,
            }
        )

    return {"items": items, "total": total}


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    country: str | None = None
    industry: str | None = None


@router.post("/tenants", status_code=status.HTTP_201_CREATED)
async def create_tenant(
    payload: TenantCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    _require_platform(ctx)

    org = Organization(
        name=payload.name,
        country=payload.country,
        industry=payload.industry,
        setup_completed=False,
        status="active",
    )
    session.add(org)
    await session.flush()
    await _audit_platform(
        session,
        ctx,
        entity_type="Organization",
        entity_id=org.id,
        organization_id=org.id,
        action="platform_tenant_created",
        changes=payload.model_dump(),
    )
    return {"id": org.id, "name": org.name, "created": True}


@router.get("/tenants/{tenant_id}")
async def get_tenant(
    tenant_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    _require_platform(ctx)
    org = await _get_tenant_or_raise(session, tenant_id)
    return {
        "id": org.id,
        "name": org.name,
        "country": org.country,
        "industry": org.industry,
        "default_currency": org.default_currency,
        "status": org.status,
        "setup_completed": org.setup_completed,
    }


class TenantUpdate(BaseModel):
    name: str | None = None
    country: str | None = None
    industry: str | None = None
    status: str | None = Field(default=None, pattern=r"^(active|suspended|archived)$")


@router.patch("/tenants/{tenant_id}")
async def update_tenant(
    tenant_id: int,
    payload: TenantUpdate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    _require_platform(ctx)
    org = await _get_tenant_or_raise(session, tenant_id)
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(org, key, value)
    await session.flush()
    await _audit_platform(
        session,
        ctx,
        entity_type="Organization",
        entity_id=org.id,
        organization_id=org.id,
        action="platform_tenant_updated",
        changes=changes,
    )
    return {"id": org.id, "name": org.name, "updated": True}


@router.post("/tenants/{tenant_id}/suspend")
async def suspend_tenant(
    tenant_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    _require_platform(ctx)
    org = await _get_tenant_or_raise(session, tenant_id)
    org.status = "suspended"
    await session.flush()
    await _audit_platform(
        session,
        ctx,
        entity_type="Organization",
        entity_id=org.id,
        organization_id=org.id,
        action="platform_tenant_suspended",
    )
    return {"id": org.id, "status": "suspended"}


@router.post("/tenants/{tenant_id}/reactivate")
async def reactivate_tenant(
    tenant_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    _require_platform(ctx)
    org = await _get_tenant_or_raise(session, tenant_id)
    org.status = "active"
    await session.flush()
    await _audit_platform(
        session,
        ctx,
        entity_type="Organization",
        entity_id=org.id,
        organization_id=org.id,
        action="platform_tenant_reactivated",
    )
    return {"id": org.id, "status": "active"}


@router.patch("/tenants/{tenant_id}/archive")
async def archive_tenant(
    tenant_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    _require_platform(ctx)
    org = await _get_tenant_or_raise(session, tenant_id)
    org.status = "archived"
    await session.flush()
    await _audit_platform(
        session,
        ctx,
        entity_type="Organization",
        entity_id=org.id,
        organization_id=org.id,
        action="platform_tenant_archived",
    )
    return {"id": org.id, "status": "archived"}


@router.get("/config/self-registration")
async def get_self_registration_config(
    ctx: RequestContext = Depends(get_current_context),
):
    _require_platform(ctx)
    return {"allow_self_registration": settings.allow_self_registration}


class SelfRegistrationUpdate(BaseModel):
    allow_self_registration: bool


@router.patch("/config/self-registration")
async def update_self_registration_config(
    payload: SelfRegistrationUpdate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    _require_platform(ctx)
    settings.allow_self_registration = payload.allow_self_registration
    await _audit_platform(
        session,
        ctx,
        entity_type="PlatformSettings",
        entity_id=None,
        action="platform_self_registration_updated",
        changes={"allow_self_registration": payload.allow_self_registration},
    )
    return {"allow_self_registration": settings.allow_self_registration}


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
            {"id": user.id, "email": user.email, "full_name": user.full_name, "is_active": user.is_active}
            for user in users
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
    await _get_tenant_or_raise(session, tenant_id)

    user_result = await session.execute(select(User).where(User.id == payload.user_id))
    if not user_result.scalar_one_or_none():
        raise AppError("NOT_FOUND", 404, f"User {payload.user_id} not found")

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
    await _audit_platform(
        session,
        ctx,
        entity_type="RoleBinding",
        entity_id=binding.id,
        organization_id=tenant_id,
        action="platform_tenant_admin_assigned",
        changes={"user_id": payload.user_id, "role": "admin"},
    )
    return {"user_id": payload.user_id, "tenant_id": tenant_id, "role": "admin"}


@router.post("/jobs/sla-check")
async def run_sla_check(
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    _require_platform(ctx)
    result = await SLAService(session).check_sla_breaches()
    await _audit_platform(
        session,
        ctx,
        entity_type="ScheduledJob",
        action="platform_sla_check_triggered",
        changes=result,
    )
    return result


@router.post("/jobs/project-deadlines")
async def run_project_deadline_check(
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    _require_platform(ctx)
    result = await SLAService(session).check_project_deadlines()
    await _audit_platform(
        session,
        ctx,
        entity_type="ScheduledJob",
        action="platform_project_deadline_check_triggered",
        changes=result,
    )
    return result


@router.post("/jobs/webhook-retries")
async def run_webhook_retries(
    limit: int = Query(100, ge=1, le=500),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    _require_platform(ctx)
    result = await WebhookService(
        repo=WebhookRepository(session),
        notification_repo=NotificationRepository(session),
    ).retry_due_deliveries(limit=limit)
    await _audit_platform(
        session,
        ctx,
        entity_type="ScheduledJob",
        action="platform_webhook_retry_triggered",
        changes=result,
    )
    return result


@router.post("/jobs/run-all")
async def run_all_jobs(
    limit: int = Query(100, ge=1, le=500),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    _require_platform(ctx)
    sla_result = await SLAService(session).check_sla_breaches()
    project_deadlines = await SLAService(session).check_project_deadlines()
    webhook_retries = await WebhookService(
        repo=WebhookRepository(session),
        notification_repo=NotificationRepository(session),
    ).retry_due_deliveries(limit=limit)
    result = {
        "sla_check": sla_result,
        "project_deadlines": project_deadlines,
        "webhook_retries": webhook_retries,
    }
    await _audit_platform(
        session,
        ctx,
        entity_type="ScheduledJob",
        action="platform_all_jobs_triggered",
        changes=result,
    )
    return result
