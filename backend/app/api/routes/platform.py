from fastapi import APIRouter, Cookie, Depends, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_cookies import (
    SUPPORT_SESSION_COOKIE_NAME,
    clear_current_organization_cookie,
    clear_support_session_cookie,
    set_current_organization_cookie,
    set_support_session_cookie,
)
from app.core.dependencies import (
    RequestContext,
    get_current_context,
    get_current_onboarding_context,
)
from app.core.exceptions import AppError
from app.db.session import get_session
from app.repositories.audit_repo import AuditRepository
from app.repositories.export_repo import ExportRepository
from app.repositories.notification_repo import NotificationRepository
from app.repositories.platform_repo import PlatformRepository
from app.repositories.webhook_repo import WebhookRepository
from app.services.export_service import ExportService
from app.services.platform_service import PlatformService
from app.services.sla_service import SLAService
from app.services.webhook_service import WebhookService
from app.workers.job_runner import JobRunner

router = APIRouter(prefix="/api/platform", tags=["Platform Admin"])


def _get_service(session: AsyncSession) -> PlatformService:
    return PlatformService(
        repo=PlatformRepository(session),
        audit_repo=AuditRepository(session),
    )


# -- Tenants ------------------------------------------------------------------


@router.get("/tenants")
async def list_tenants(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).list_tenants(ctx, page=page, page_size=page_size)


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
    org = await _get_service(session).create_tenant(
        ctx, name=payload.name, country=payload.country, industry=payload.industry
    )
    return {"id": org.id, "name": org.name, "created": True}


@router.get("/tenants/{tenant_id}")
async def get_tenant(
    tenant_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    org = await _get_service(session).get_tenant(ctx, tenant_id)
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

    model_config = {"extra": "forbid"}


@router.patch("/tenants/{tenant_id}")
async def update_tenant(
    tenant_id: int,
    payload: TenantUpdate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    org = await _get_service(session).update_tenant(
        ctx, tenant_id, payload.model_dump(exclude_unset=True)
    )
    return {"id": org.id, "name": org.name, "updated": True}


@router.post("/tenants/{tenant_id}/suspend")
async def suspend_tenant(
    tenant_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    org = await _get_service(session).set_tenant_status(ctx, tenant_id, "suspended")
    return {"id": org.id, "status": "suspended"}


@router.post("/tenants/{tenant_id}/reactivate")
async def reactivate_tenant(
    tenant_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    org = await _get_service(session).set_tenant_status(ctx, tenant_id, "active")
    return {"id": org.id, "status": "active"}


@router.patch("/tenants/{tenant_id}/archive")
async def archive_tenant(
    tenant_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    org = await _get_service(session).set_tenant_status(ctx, tenant_id, "archived")
    return {"id": org.id, "status": "archived"}


# -- Config -------------------------------------------------------------------


@router.get("/config/self-registration")
async def get_self_registration_config(
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    value = await _get_service(session).get_self_registration(ctx)
    return {"allow_self_registration": value}


class SelfRegistrationUpdate(BaseModel):
    allow_self_registration: bool


@router.patch("/config/self-registration")
async def update_self_registration_config(
    payload: SelfRegistrationUpdate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    value = await _get_service(session).set_self_registration(ctx, payload.allow_self_registration)
    return {"allow_self_registration": value}


# -- Users (platform-level) ---------------------------------------------------


@router.get("/users")
async def list_platform_users(
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return {"items": await _get_service(session).list_users(ctx)}


class AssignAdminRequest(BaseModel):
    user_id: int


@router.post("/tenants/{tenant_id}/admins")
async def assign_admin(
    tenant_id: int,
    payload: AssignAdminRequest,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    await _get_service(session).assign_tenant_admin(ctx, tenant_id, payload.user_id)
    return {"user_id": payload.user_id, "tenant_id": tenant_id, "role": "admin"}


# -- Metrics ------------------------------------------------------------------


@router.get("/metrics")
async def get_platform_metrics(
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).get_platform_metrics(ctx)


# -- Cross-tenant user management ---------------------------------------------


@router.get("/tenants/{tenant_id}/users")
async def list_tenant_users(
    tenant_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    users = await _get_service(session).list_tenant_users(ctx, tenant_id)
    return {"items": users, "total": len(users)}


# -- Jobs (background tasks) --------------------------------------------------


@router.get("/jobs/status")
async def get_job_status(
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    _get_service(session)._require_platform(ctx)
    return await JobRunner().collect_status_from_session(session)


@router.post("/jobs/sla-check")
async def run_sla_check(
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    svc = _get_service(session)
    svc._require_platform(ctx)
    result = await SLAService(session).check_sla_breaches()
    await svc._audit(
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
    svc = _get_service(session)
    svc._require_platform(ctx)
    result = await SLAService(session).check_project_deadlines()
    await svc._audit(
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
    svc = _get_service(session)
    svc._require_platform(ctx)
    result = await WebhookService(
        repo=WebhookRepository(session),
        notification_repo=NotificationRepository(session),
    ).retry_due_deliveries(limit=limit)
    await svc._audit(
        ctx,
        entity_type="ScheduledJob",
        action="platform_webhook_retry_triggered",
        changes=result,
    )
    return result


@router.post("/jobs/exports")
async def run_export_jobs(
    limit: int = Query(25, ge=1, le=500),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    svc = _get_service(session)
    svc._require_platform(ctx)
    result = await ExportService(
        session,
        repo=ExportRepository(session),
        audit_repo=AuditRepository(session),
    ).process_queued_jobs(limit=limit)
    await svc._audit(
        ctx,
        entity_type="ScheduledJob",
        action="platform_export_jobs_triggered",
        changes=result,
    )
    return result


@router.post("/jobs/run-all")
async def run_all_jobs(
    limit: int = Query(100, ge=1, le=500),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    svc = _get_service(session)
    svc._require_platform(ctx)
    sla_result = await SLAService(session).check_sla_breaches()
    project_deadlines = await SLAService(session).check_project_deadlines()
    webhook_retries = await WebhookService(
        repo=WebhookRepository(session),
        notification_repo=NotificationRepository(session),
    ).retry_due_deliveries(limit=limit)
    export_jobs = await ExportService(
        session,
        repo=ExportRepository(session),
        audit_repo=AuditRepository(session),
    ).process_queued_jobs(limit=limit)
    result = {
        "sla_check": sla_result,
        "project_deadlines": project_deadlines,
        "webhook_retries": webhook_retries,
        "export_jobs": export_jobs,
    }
    await svc._audit(
        ctx,
        entity_type="ScheduledJob",
        action="platform_all_jobs_triggered",
        changes=result,
    )
    return result


# -- Support Mode --------------------------------------------------------------


class SupportSessionRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class SupportSessionCurrentOut(BaseModel):
    active: bool
    session_id: int | None = None
    tenant_id: int | None = None
    tenant_name: str | None = None
    started_at: str | None = None


@router.post("/tenants/{tenant_id}/support-session")
async def start_support_session(
    tenant_id: int,
    payload: SupportSessionRequest,
    response: Response,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    ss = await _get_service(session).start_support_session(ctx, tenant_id, payload.reason)
    set_support_session_cookie(response, ss.id)
    set_current_organization_cookie(response, tenant_id)
    return {
        "session_id": ss.id,
        "tenant_id": tenant_id,
        "started_at": ss.started_at.isoformat() if ss.started_at else None,
    }


@router.get("/support-session/current", response_model=SupportSessionCurrentOut)
async def get_current_support_session(
    response: Response,
    support_session_cookie: str | None = Cookie(default=None, alias=SUPPORT_SESSION_COOKIE_NAME),
    ctx: RequestContext = Depends(get_current_onboarding_context),
    session: AsyncSession = Depends(get_session),
):
    svc = _get_service(session)
    svc._require_platform(ctx)
    if not support_session_cookie:
        return SupportSessionCurrentOut(active=False)

    try:
        session_id = int(support_session_cookie)
    except ValueError:
        clear_support_session_cookie(response)
        clear_current_organization_cookie(response)
        return SupportSessionCurrentOut(active=False)

    current = await svc.get_current_support_session(ctx, session_id)
    if not current:
        clear_support_session_cookie(response)
        clear_current_organization_cookie(response)
        return SupportSessionCurrentOut(active=False)

    return SupportSessionCurrentOut(active=True, **current)


@router.delete("/support-session/current")
async def end_current_support_session(
    response: Response,
    support_session_cookie: str | None = Cookie(default=None, alias=SUPPORT_SESSION_COOKIE_NAME),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    if not support_session_cookie:
        raise AppError("NOT_FOUND", 404, "Support session not found")
    try:
        session_id = int(support_session_cookie)
    except ValueError as exc:
        raise AppError("INVALID_SUPPORT_SESSION", 400, "Support session cookie is invalid") from exc

    ss = await _get_service(session).end_support_session(ctx, session_id)
    clear_support_session_cookie(response)
    clear_current_organization_cookie(response)
    return {"session_id": ss.id, "ended_at": ss.ended_at.isoformat()}


@router.delete("/support-session/{session_id}")
async def end_support_session(
    session_id: int,
    response: Response,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    ss = await _get_service(session).end_support_session(ctx, session_id)
    clear_support_session_cookie(response)
    clear_current_organization_cookie(response)
    return {"session_id": ss.id, "ended_at": ss.ended_at.isoformat()}
