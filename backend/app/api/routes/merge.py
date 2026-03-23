from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.services.merge_service import MergeService

router = APIRouter(tags=["Merge"])


@router.get("/api/projects/{project_id}/merge")
async def get_merged_view(
    project_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    service = MergeService(session)
    return await service.get_merged_view(project_id, ctx)


@router.get("/api/projects/{project_id}/merge/coverage")
async def get_coverage(
    project_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    service = MergeService(session)
    return await service.get_coverage(project_id, ctx)
