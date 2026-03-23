from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.services.export_service import ExportService

router = APIRouter(tags=["Export"])


@router.get("/api/projects/{project_id}/export/readiness")
async def readiness_check(
    project_id: int,
    session: AsyncSession = Depends(get_session),
):
    service = ExportService(session)
    return await service.readiness_check(project_id)


@router.post("/api/projects/{project_id}/publish")
async def publish(
    project_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    service = ExportService(session)
    return await service.publish(project_id)
