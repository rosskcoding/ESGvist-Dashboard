from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.repositories.audit_repo import AuditRepository
from app.repositories.export_repo import ExportRepository
from app.repositories.project_repo import ProjectRepository
from app.schemas.export import ExportJobCreate
from app.services.export_service import ExportService
from app.services.project_service import ProjectService

router = APIRouter(tags=["Export"])


def _project_service(session: AsyncSession) -> ProjectService:
    return ProjectService(
        repo=ProjectRepository(session),
        audit_repo=AuditRepository(session),
    )


def _export_service(session: AsyncSession) -> ExportService:
    return ExportService(
        session,
        repo=ExportRepository(session),
        audit_repo=AuditRepository(session),
    )


@router.get("/api/projects/{project_id}/export/readiness")
async def readiness_check(
    project_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    service = _export_service(session)
    return await service.readiness_check(project_id, ctx)


@router.post("/api/projects/{project_id}/exports", status_code=201)
async def queue_export_job(
    project_id: int,
    payload: ExportJobCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _export_service(session).queue_export_job(project_id, payload, ctx)


@router.get("/api/projects/{project_id}/exports")
async def list_export_jobs(
    project_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _export_service(session).list_export_jobs(project_id, ctx, page, page_size)


@router.get("/api/exports/{job_id}")
async def get_export_job(
    job_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _export_service(session).get_export_job(job_id, ctx)


@router.get("/api/exports/{job_id}/artifact")
async def get_export_artifact(
    job_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _export_service(session).get_export_artifact(job_id, ctx)


@router.post("/api/projects/{project_id}/publish")
async def publish(
    project_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _project_service(session).publish_project(project_id, ctx)
