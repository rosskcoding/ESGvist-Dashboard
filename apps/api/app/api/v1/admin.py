"""
Admin API endpoints — Platform operations for superusers.

ESGvist Dashboard admin:
- GET /admin/overview — platform stats (companies, users, ESG metrics/facts)
- GET /admin/audit-events — cross-tenant audit log
- GET /admin/health — admin health check
"""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user_required
from app.domain.models import (
    AuditEvent,
    Company,
    CompanyStatus,
    EsgFact,
    EsgMetric,
    User,
)
from app.infra.database import get_session

router = APIRouter(prefix="/admin", tags=["Admin"])

CurrentUser = Annotated[User, Depends(get_current_user_required)]
DB = Annotated[AsyncSession, Depends(get_session)]


async def require_superuser(user: CurrentUser) -> User:
    """Dependency that enforces superuser access."""
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser access required",
        )
    return user


SuperUser = Annotated[User, Depends(require_superuser)]


# ── Schemas ──────────────────────────────────────────────────────────────


class PlatformOverviewResponse(BaseModel):
    total_companies: int
    active_companies: int
    total_users: int
    active_users: int
    total_metrics: int
    total_facts: int


class AuditEventListItem(BaseModel):
    event_id: UUID
    action: str
    user_id: UUID | None
    user_email: str | None
    company_id: UUID | None
    target_type: str | None
    target_id: str | None
    detail: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditEventListResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[AuditEventListItem]


# ── Endpoints ────────────────────────────────────────────────────────────


@router.get("/overview", response_model=PlatformOverviewResponse)
async def get_platform_overview(
    _su: SuperUser,
    db: DB,
) -> PlatformOverviewResponse:
    """Platform-wide statistics for the superuser dashboard."""
    total_companies = (await db.execute(select(func.count(Company.company_id)))).scalar() or 0
    active_companies = (
        await db.execute(
            select(func.count(Company.company_id)).where(Company.status == CompanyStatus.ACTIVE)
        )
    ).scalar() or 0
    total_users = (await db.execute(select(func.count(User.user_id)))).scalar() or 0
    active_users = (
        await db.execute(select(func.count(User.user_id)).where(User.is_active.is_(True)))
    ).scalar() or 0
    total_metrics = (await db.execute(select(func.count(EsgMetric.metric_id)))).scalar() or 0
    total_facts = (await db.execute(select(func.count(EsgFact.fact_id)))).scalar() or 0

    return PlatformOverviewResponse(
        total_companies=total_companies,
        active_companies=active_companies,
        total_users=total_users,
        active_users=active_users,
        total_metrics=total_metrics,
        total_facts=total_facts,
    )


@router.get("/audit-events", response_model=AuditEventListResponse)
async def list_audit_events(
    _su: SuperUser,
    db: DB,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    action: str | None = None,
    company_id: UUID | None = None,
) -> AuditEventListResponse:
    """Cross-tenant audit event log."""
    base = select(AuditEvent)
    count_q = select(func.count(AuditEvent.event_id))

    if action:
        base = base.where(AuditEvent.action == action)
        count_q = count_q.where(AuditEvent.action == action)
    if company_id:
        base = base.where(AuditEvent.company_id == company_id)
        count_q = count_q.where(AuditEvent.company_id == company_id)

    total = (await db.execute(count_q)).scalar() or 0

    rows = (
        await db.execute(
            base.order_by(AuditEvent.created_at_utc.desc()).offset(offset).limit(limit)
        )
    ).scalars().all()

    return AuditEventListResponse(
        total=total,
        offset=offset,
        limit=limit,
        items=[
            AuditEventListItem(
                event_id=e.event_id,
                action=e.action,
                user_id=e.user_id,
                user_email=e.user_email,
                company_id=e.company_id,
                target_type=e.target_type,
                target_id=str(e.target_id) if e.target_id else None,
                detail=e.detail,
                created_at=e.created_at_utc,
            )
            for e in rows
        ],
    )


@router.get("/health")
async def admin_health() -> dict:
    """Admin health check."""
    return {"status": "ok", "service": "esgvist-dashboard"}
