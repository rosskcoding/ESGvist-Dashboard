from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services.reuse_service import ReuseService

router = APIRouter(tags=["Reuse"])


@router.get("/api/projects/{project_id}/data-points/find-reuse")
async def find_reuse(
    project_id: int,
    shared_element_id: int = Query(...),
    unit_code: str | None = None,
    entity_id: int | None = None,
    session: AsyncSession = Depends(get_session),
):
    service = ReuseService(session)
    return await service.find_reuse(project_id, shared_element_id, unit_code, entity_id)


@router.get("/api/data-points/{dp_id}/reuse-info")
async def reuse_info(
    dp_id: int,
    session: AsyncSession = Depends(get_session),
):
    service = ReuseService(session)
    return await service.get_reuse_info(dp_id)
