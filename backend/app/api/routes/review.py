from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.repositories.audit_repo import AuditRepository
from app.repositories.data_point_repo import DataPointRepository
from app.repositories.notification_repo import NotificationRepository
from app.services.review_service import ReviewService

router = APIRouter(prefix="/api/review", tags=["Review"])


class BatchApproveAction(BaseModel):
    data_point_ids: list[int]
    comment: str | None = None


class BatchRejectAction(BaseModel):
    data_point_ids: list[int]
    comment: str | None = None


class BatchRevisionAction(BaseModel):
    data_point_ids: list[int]
    comment: str | None = None


def _get_service(session: AsyncSession) -> ReviewService:
    return ReviewService(
        dp_repo=DataPointRepository(session),
        audit_repo=AuditRepository(session),
        notification_repo=NotificationRepository(session),
    )


@router.post("/batch-approve")
async def batch_approve(
    payload: BatchApproveAction,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).batch_approve(payload.data_point_ids, payload.comment, ctx)


@router.get("/items")
async def list_review_items(
    project_id: int | None = None,
    statuses: str = Query("submitted,in_review"),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    normalized_statuses = [status.strip() for status in statuses.split(",") if status.strip()]
    return await _get_service(session).list_review_items(ctx, project_id, normalized_statuses)


@router.post("/batch-reject")
async def batch_reject(
    payload: BatchRejectAction,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).batch_reject(payload.data_point_ids, payload.comment, ctx)


@router.post("/batch-request-revision")
async def batch_request_revision(
    payload: BatchRevisionAction,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).batch_request_revision(payload.data_point_ids, payload.comment, ctx)
