from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.models.audit_log import AuditLog
from app.db.session import get_session

router = APIRouter(prefix="/api/audit-log", tags=["Audit"])


@router.get("")
async def list_audit_log(
    entity_type: str | None = None,
    user_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    q = select(AuditLog).order_by(AuditLog.created_at.desc())

    if ctx.organization_id:
        q = q.where(AuditLog.organization_id == ctx.organization_id)
    if entity_type:
        q = q.where(AuditLog.entity_type == entity_type)
    if user_id:
        q = q.where(AuditLog.user_id == user_id)

    q = q.offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(q)
    items = result.scalars().all()

    return {
        "items": [
            {
                "id": a.id,
                "entity_type": a.entity_type,
                "entity_id": a.entity_id,
                "action": a.action,
                "user_id": a.user_id,
                "changes": a.changes,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in items
        ]
    }
