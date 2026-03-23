from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services.merge_service import MergeService

router = APIRouter(tags=["Merge"])


@router.get("/api/projects/{project_id}/merge")
async def get_merged_view(
    project_id: int,
    session: AsyncSession = Depends(get_session),
):
    service = MergeService(session)
    return await service.get_merged_view(project_id)


@router.get("/api/projects/{project_id}/merge/coverage")
async def get_coverage(
    project_id: int,
    session: AsyncSession = Depends(get_session),
):
    service = MergeService(session)
    return await service.get_coverage(project_id)
