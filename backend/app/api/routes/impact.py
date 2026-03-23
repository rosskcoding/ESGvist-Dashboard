from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.services.impact_service import ImpactService

router = APIRouter(prefix="/api/impact", tags=["Impact Analysis"])


@router.get("/requirement-item/{item_id}")
async def preview_requirement_change(
    item_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    service = ImpactService(session)
    return await service.preview_requirement_change(item_id, ctx)


@router.get("/mapping/{mapping_id}")
async def preview_mapping_change(
    mapping_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    service = ImpactService(session)
    return await service.preview_mapping_change(mapping_id, ctx)


@router.get("/boundary/preview")
async def preview_boundary_change(
    project_id: int = Query(...),
    new_boundary_id: int = Query(...),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    service = ImpactService(session)
    return await service.preview_boundary_change(project_id, new_boundary_id, ctx)
