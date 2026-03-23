from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.policies.auth_policy import AuthPolicy
from app.repositories.project_repo import ProjectRepository
from app.schemas.projects import (
    AssignmentBulkUpdate,
    AssignmentCreate,
    AssignmentInlineUpdate,
    AssignmentMatrixOut,
    AssignmentMatrixRowOut,
    AssignmentOut,
    BoundaryDefUpdate,
    BoundaryMembershipListOut,
    BoundaryMembershipReplaceRequest,
    BoundaryDefCreate,
    BoundaryDefOut,
    ProjectBoundaryOut,
    ProjectCreate,
    ProjectAssignmentSummaryListOut,
    ProjectListOut,
    ProjectOut,
    ProjectStandardSummaryListOut,
    ProjectStandardAdd,
)
from app.repositories.audit_repo import AuditRepository
from app.services.boundary_service import BoundaryService
from app.services.impact_service import ImpactService
from app.services.project_service import ProjectService

router = APIRouter(tags=["Projects"])


class ProjectWorkflowAction(BaseModel):
    comment: str | None = None


def _get_service(session: AsyncSession) -> ProjectService:
    return ProjectService(repo=ProjectRepository(session), audit_repo=AuditRepository(session))


def _get_boundary_service(session: AsyncSession) -> BoundaryService:
    return BoundaryService(session=session, audit_repo=AuditRepository(session))


# --- Projects ---
@router.post("/api/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.auditor_read_only(ctx)
    return await _get_service(session).create_project(payload, ctx)


@router.get("/api/projects", response_model=ProjectListOut)
async def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).list_projects(ctx, page, page_size)


@router.get("/api/projects/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).get_project(project_id, ctx)


@router.post("/api/projects/{project_id}/standards")
async def add_standard(
    project_id: int,
    payload: ProjectStandardAdd,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.auditor_read_only(ctx)
    return await _get_service(session).add_standard(project_id, payload, ctx)


@router.get("/api/projects/{project_id}/standards", response_model=ProjectStandardSummaryListOut)
async def list_project_standards(
    project_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).list_project_standards(project_id, ctx)


# --- Assignments ---
@router.post(
    "/api/projects/{project_id}/assignments",
    response_model=AssignmentOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_assignment(
    project_id: int,
    payload: AssignmentCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.auditor_read_only(ctx)
    return await _get_service(session).create_assignment(project_id, payload, ctx)


@router.get("/api/projects/{project_id}/assignments", response_model=AssignmentMatrixOut)
async def list_assignments(
    project_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).list_assignments(project_id, ctx)


@router.get("/api/projects/{project_id}/assignments/summary", response_model=ProjectAssignmentSummaryListOut)
async def get_assignment_summary(
    project_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).get_assignment_summary(project_id, ctx)


@router.patch("/api/projects/{project_id}/assignments/inline-update", response_model=AssignmentMatrixRowOut)
async def inline_update_assignment(
    project_id: int,
    payload: AssignmentInlineUpdate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.auditor_read_only(ctx)
    return await _get_service(session).inline_update_assignment(project_id, payload, ctx)


@router.patch("/api/projects/{project_id}/assignments/bulk-update")
async def bulk_update_assignments(
    project_id: int,
    payload: AssignmentBulkUpdate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.auditor_read_only(ctx)
    return await _get_service(session).bulk_update_assignments(project_id, payload, ctx)


# --- Boundaries ---
@router.post("/api/boundaries", response_model=BoundaryDefOut, status_code=status.HTTP_201_CREATED)
async def create_boundary(
    payload: BoundaryDefCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.auditor_read_only(ctx)
    return await _get_service(session).create_boundary(payload, ctx)


@router.get("/api/boundaries", response_model=list[BoundaryDefOut])
async def list_boundaries(
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).list_boundaries(ctx)


@router.get("/api/boundaries/{boundary_id}", response_model=BoundaryDefOut)
async def get_boundary(
    boundary_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_boundary_service(session).get_boundary(boundary_id, ctx)


@router.patch("/api/boundaries/{boundary_id}", response_model=BoundaryDefOut)
async def update_boundary(
    boundary_id: int,
    payload: BoundaryDefUpdate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.auditor_read_only(ctx)
    return await _get_boundary_service(session).update_boundary(boundary_id, payload, ctx)


@router.get("/api/boundaries/{boundary_id}/memberships", response_model=BoundaryMembershipListOut)
async def list_boundary_memberships(
    boundary_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_boundary_service(session).list_memberships(boundary_id, ctx)


@router.put("/api/boundaries/{boundary_id}/memberships", response_model=BoundaryMembershipListOut)
async def replace_boundary_memberships(
    boundary_id: int,
    payload: BoundaryMembershipReplaceRequest,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.auditor_read_only(ctx)
    return await _get_boundary_service(session).replace_memberships(boundary_id, payload, ctx)


@router.post("/api/boundaries/{boundary_id}/recalculate")
async def recalculate_boundary_memberships(
    boundary_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.auditor_read_only(ctx)
    return await _get_boundary_service(session).recalculate_memberships(boundary_id, ctx)


@router.put("/api/projects/{project_id}/boundary", response_model=ProjectOut)
async def apply_boundary(
    project_id: int,
    boundary_id: int = Query(...),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.auditor_read_only(ctx)
    return await _get_service(session).apply_boundary(project_id, boundary_id, ctx)


@router.get("/api/projects/{project_id}/boundary", response_model=ProjectBoundaryOut)
async def get_project_boundary(
    project_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_boundary_service(session).get_project_boundary(project_id, ctx)


@router.get("/api/projects/{project_id}/boundary/assignments-preview")
async def preview_boundary_assignment_changes(
    project_id: int,
    boundary_id: int = Query(...),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await ImpactService(session).preview_boundary_change(project_id, boundary_id, ctx)


@router.post("/api/projects/{project_id}/start")
async def start_project(
    project_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.auditor_read_only(ctx)
    return await _get_service(session).start_project(project_id, ctx)


@router.post("/api/projects/{project_id}/activate")
async def activate_project(
    project_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.auditor_read_only(ctx)
    return await _get_service(session).start_project(project_id, ctx)


@router.post("/api/projects/{project_id}/review")
async def review_project(
    project_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.auditor_read_only(ctx)
    return await _get_service(session).review_project(project_id, ctx)


@router.post("/api/projects/{project_id}/start-review")
async def start_project_review(
    project_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.auditor_read_only(ctx)
    return await _get_service(session).review_project(project_id, ctx)


@router.post("/api/projects/{project_id}/rollback")
async def rollback_project(
    project_id: int,
    payload: ProjectWorkflowAction,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.auditor_read_only(ctx)
    return await _get_service(session).rollback_project(project_id, payload.comment, ctx)
