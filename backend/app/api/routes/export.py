from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.repositories.audit_repo import AuditRepository
from app.repositories.export_repo import ExportRepository
from app.repositories.idempotency_repo import IdempotencyRepository
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
        idempotency_repo=IdempotencyRepository(session),
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
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _export_service(session).queue_export_job(
        project_id,
        payload,
        ctx,
        idempotency_key=x_idempotency_key,
    )


@router.post("/api/projects/{project_id}/export/gri-index", status_code=201)
async def queue_gri_content_index(
    project_id: int,
    export_format: str = Query("pdf", pattern=r"^(pdf|xlsx|csv)$"),
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _export_service(session).queue_export_job(
        project_id,
        ExportJobCreate(export_format=export_format, report_type="gri_content_index"),
        ctx,
        idempotency_key=x_idempotency_key,
    )


@router.post("/api/projects/{project_id}/export/report", status_code=201)
async def queue_project_report(
    project_id: int,
    export_format: str = Query("pdf", pattern=r"^(pdf|xlsx|json|csv)$"),
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _export_service(session).queue_export_job(
        project_id,
        ExportJobCreate(export_format=export_format, report_type="project_report"),
        ctx,
        idempotency_key=x_idempotency_key,
    )


@router.post("/api/projects/{project_id}/export/xbrl", status_code=201)
async def queue_xbrl_export(
    project_id: int,
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _export_service(session).queue_export_job(
        project_id,
        ExportJobCreate(export_format="xml", report_type="xbrl_instance"),
        ctx,
        idempotency_key=x_idempotency_key,
    )


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
