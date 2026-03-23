from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.repositories.data_point_repo import DataPointRepository
from app.services.review_service import ReviewService

router = APIRouter(prefix="/api/review", tags=["Review"])


class BatchAction(BaseModel):
    data_point_ids: list[int]
    comment: str | None = None


def _get_service(session: AsyncSession) -> ReviewService:
    return ReviewService(dp_repo=DataPointRepository(session))


@router.post("/batch-approve")
async def batch_approve(
    payload: BatchAction,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).batch_approve(payload.data_point_ids, payload.comment, ctx)


@router.post("/batch-reject")
async def batch_reject(
    payload: BatchAction,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).batch_reject(payload.data_point_ids, payload.comment, ctx)
