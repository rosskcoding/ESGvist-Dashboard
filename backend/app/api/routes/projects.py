from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.repositories.project_repo import ProjectRepository
from app.schemas.projects import (
    AssignmentCreate,
    AssignmentOut,
    BoundaryDefCreate,
    BoundaryDefOut,
    ProjectCreate,
    ProjectListOut,
    ProjectOut,
    ProjectStandardAdd,
)
from app.services.project_service import ProjectService

router = APIRouter(tags=["Projects"])


def _get_service(session: AsyncSession) -> ProjectService:
    return ProjectService(repo=ProjectRepository(session))


# --- Projects ---
@router.post("/api/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
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
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).get_project(project_id)


@router.post("/api/projects/{project_id}/standards")
async def add_standard(
    project_id: int,
    payload: ProjectStandardAdd,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).add_standard(project_id, payload, ctx)


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
    return await _get_service(session).create_assignment(project_id, payload, ctx)


@router.get("/api/projects/{project_id}/assignments", response_model=list[AssignmentOut])
async def list_assignments(
    project_id: int,
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).list_assignments(project_id)


# --- Boundaries ---
@router.post("/api/boundaries", response_model=BoundaryDefOut, status_code=status.HTTP_201_CREATED)
async def create_boundary(
    payload: BoundaryDefCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).create_boundary(payload, ctx)


@router.get("/api/boundaries", response_model=list[BoundaryDefOut])
async def list_boundaries(
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).list_boundaries(ctx)


@router.put("/api/projects/{project_id}/boundary", response_model=ProjectOut)
async def apply_boundary(
    project_id: int,
    boundary_id: int = Query(...),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).apply_boundary(project_id, boundary_id, ctx)
