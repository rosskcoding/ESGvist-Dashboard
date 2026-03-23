from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.repositories.audit_repo import AuditRepository
from app.repositories.project_repo import ProjectRepository
from app.services.export_service import ExportService
from app.services.project_service import ProjectService

router = APIRouter(tags=["Export"])


def _project_service(session: AsyncSession) -> ProjectService:
    return ProjectService(
        repo=ProjectRepository(session),
        audit_repo=AuditRepository(session),
    )


@router.get("/api/projects/{project_id}/export/readiness")
async def readiness_check(
    project_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    service = ExportService(session)
    return await service.readiness_check(project_id, ctx)


@router.post("/api/projects/{project_id}/publish")
async def publish(
    project_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _project_service(session).publish_project(project_id, ctx)
