from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.repositories.audit_repo import AuditRepository
from app.schemas.audit import AuditLogExportOut, AuditLogListOut
from app.services.audit_service import AuditService

router = APIRouter(prefix="/api/audit-log", tags=["Audit"])


def _get_service(session: AsyncSession) -> AuditService:
    return AuditService(AuditRepository(session))


@router.get("", response_model=AuditLogListOut)
async def list_audit_log(
    organization_id: int | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    action: str | None = None,
    user_id: int | None = None,
    request_id: str | None = None,
    performed_by_platform_admin: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).list_logs(
        ctx=ctx,
        organization_id=organization_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        user_id=user_id,
        request_id=request_id,
        performed_by_platform_admin=performed_by_platform_admin,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )


@router.get("/export", response_model=AuditLogExportOut)
async def export_audit_log(
    format: str = Query("csv", pattern=r"^(csv|json)$"),
    organization_id: int | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    action: str | None = None,
    user_id: int | None = None,
    request_id: str | None = None,
    performed_by_platform_admin: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).export_logs(
        export_format=format,
        ctx=ctx,
        organization_id=organization_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        user_id=user_id,
        request_id=request_id,
        performed_by_platform_admin=performed_by_platform_admin,
        date_from=date_from,
        date_to=date_to,
    )
