from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.core.exceptions import AppError
from app.db.session import get_session
from app.repositories.notification_repo import NotificationRepository
from app.schemas.notifications import NotificationPreferencesOut, NotificationPreferencesUpdate
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


def _get_service(session: AsyncSession) -> NotificationService:
    return NotificationService(repo=NotificationRepository(session))


def _require_notification_access(ctx: RequestContext) -> int:
    if ctx.organization_id is None:
        raise AppError("ORG_HEADER_REQUIRED", 400, "X-Organization-Id header is required")
    if ctx.role == "auditor":
        raise AppError("FORBIDDEN", 403, "Auditors cannot access notifications")
    return ctx.organization_id


@router.get("")
async def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    type: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    is_read: bool | None = Query(default=None),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    org_id = _require_notification_access(ctx)
    return await _get_service(session).list_notifications(
        ctx.user_id,
        org_id,
        page,
        page_size,
        type=type,
        severity=severity,
        is_read=is_read,
    )


@router.get("/unread-count")
async def unread_count(
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    org_id = _require_notification_access(ctx)
    return await _get_service(session).unread_count(ctx.user_id, org_id)


@router.patch("/{notification_id}/read")
async def mark_read(
    notification_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    org_id = _require_notification_access(ctx)
    return await _get_service(session).mark_read(notification_id, ctx.user_id, org_id)


@router.post("/read-all")
async def mark_all_read(
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    org_id = _require_notification_access(ctx)
    return await _get_service(session).mark_all_read(ctx.user_id, org_id)


@router.get("/digest")
async def get_digest(
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    """Return pending digest notifications for the current user."""
    org_id = _require_notification_access(ctx)
    return await _get_service(session).get_digest(ctx.user_id, org_id)


@router.get("/preferences", response_model=NotificationPreferencesOut)
async def get_preferences(
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    _require_notification_access(ctx)
    return await _get_service(session).get_preferences(ctx.user_id)


@router.patch("/preferences", response_model=NotificationPreferencesOut)
async def update_preferences(
    payload: NotificationPreferencesUpdate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    _require_notification_access(ctx)
    return await _get_service(session).update_preferences(
        ctx.user_id,
        payload.model_dump(exclude_unset=True),
    )
