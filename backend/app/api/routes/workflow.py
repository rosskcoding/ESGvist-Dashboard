from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.policies.auth_policy import AuthPolicy
from app.repositories.audit_repo import AuditRepository
from app.repositories.data_point_repo import DataPointRepository
from app.repositories.evidence_repo import EvidenceRepository
from app.repositories.export_repo import ExportRepository
from app.repositories.idempotency_repo import IdempotencyRepository
from app.services.workflow_service import WorkflowService
from app.services.export_service import ExportService

router = APIRouter(tags=["Workflow"])


class WorkflowAction(BaseModel):
    comment: str | None = None


class GateCheckDraftPayload(BaseModel):
    numeric_value: float | None = None
    text_value: str | None = None
    unit_code: str | None = None
    methodology: str | None = None


class GateCheckRequest(BaseModel):
    action: str
    data_point_id: int | None = None
    project_id: int | None = None
    comment: str | None = None
    draft: GateCheckDraftPayload | None = None
    pending_evidence_count: int = Field(default=0, ge=0)


def _get_service(session: AsyncSession) -> WorkflowService:
    return WorkflowService(
        dp_repo=DataPointRepository(session),
        evidence_repo=EvidenceRepository(session),
        audit_repo=AuditRepository(session),
    )


def _get_export_service(session: AsyncSession) -> ExportService:
    return ExportService(
        session,
        repo=ExportRepository(session),
        audit_repo=AuditRepository(session),
        idempotency_repo=IdempotencyRepository(session),
    )


@router.post("/api/data-points/{dp_id}/submit")
async def submit(
    dp_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.auditor_read_only(ctx)
    return await _get_service(session).submit(dp_id, ctx)


@router.post("/api/data-points/{dp_id}/approve")
async def approve(
    dp_id: int,
    payload: WorkflowAction = WorkflowAction(),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.auditor_read_only(ctx)
    return await _get_service(session).approve(dp_id, payload.comment, ctx)


@router.post("/api/data-points/{dp_id}/reject")
async def reject(
    dp_id: int,
    payload: WorkflowAction = WorkflowAction(),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.auditor_read_only(ctx)
    return await _get_service(session).reject(dp_id, payload.comment, ctx)


@router.post("/api/data-points/{dp_id}/request-revision")
async def request_revision(
    dp_id: int,
    payload: WorkflowAction = WorkflowAction(),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.auditor_read_only(ctx)
    return await _get_service(session).request_revision(dp_id, payload.comment, ctx)


@router.post("/api/data-points/{dp_id}/rollback")
async def rollback(
    dp_id: int,
    payload: WorkflowAction = WorkflowAction(),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.auditor_read_only(ctx)
    return await _get_service(session).rollback(dp_id, payload.comment, ctx)


@router.post("/api/gate-check")
async def gate_check(
    payload: GateCheckRequest,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    if payload.data_point_id is not None:
        return await _get_service(session).gate_check(
            payload.action,
            payload.data_point_id,
            ctx,
            payload.comment,
            draft=payload.draft.model_dump(exclude_unset=True) if payload.draft else None,
            pending_evidence_count=payload.pending_evidence_count,
        )
    if payload.project_id is not None and payload.action == "start_export":
        return await _get_export_service(session).gate_check_start_export(payload.project_id, ctx)
    raise AppError(
        "GATE_CHECK_RESOURCE_REQUIRED",
        422,
        "gate-check requires data_point_id for data point actions or project_id for start_export",
    )
