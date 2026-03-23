from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.policies.auth_policy import AuthPolicy
from app.repositories.audit_repo import AuditRepository
from app.repositories.data_point_repo import DataPointRepository
from app.services.workflow_service import WorkflowService

router = APIRouter(tags=["Workflow"])


class WorkflowAction(BaseModel):
    comment: str | None = None


class GateCheckRequest(BaseModel):
    action: str
    data_point_id: int
    comment: str | None = None


def _get_service(session: AsyncSession) -> WorkflowService:
    return WorkflowService(
        dp_repo=DataPointRepository(session),
        audit_repo=AuditRepository(session),
    )


@router.post("/api/data-points/{dp_id}/submit")
async def submit(
    dp_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.auditor_read_only(ctx)
    service = _get_service(session)
    return await service.submit(dp_id, ctx, assignment_repo=service.dp_repo)


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
    return await _get_service(session).gate_check(
        payload.action, payload.data_point_id, ctx, payload.comment
    )
