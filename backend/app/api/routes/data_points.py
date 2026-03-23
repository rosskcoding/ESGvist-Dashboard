from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.repositories.data_point_repo import DataPointRepository
from app.repositories.evidence_repo import EvidenceRepository
from app.schemas.data_points import DataPointCreate, DataPointListOut, DataPointOut
from app.schemas.evidence import (
    EvidenceCreate,
    EvidenceLinkRequest,
    EvidenceListOut,
    EvidenceOut,
)
from app.services.data_point_service import DataPointService
from app.services.evidence_service import EvidenceService

router = APIRouter(tags=["Data Points & Evidence"])


def _dp_service(session: AsyncSession) -> DataPointService:
    return DataPointService(repo=DataPointRepository(session))


def _ev_service(session: AsyncSession) -> EvidenceService:
    return EvidenceService(repo=EvidenceRepository(session))


# --- Data Points ---
@router.post(
    "/api/projects/{project_id}/data-points",
    response_model=DataPointOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_data_point(
    project_id: int,
    payload: DataPointCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _dp_service(session).create(project_id, payload, ctx)


@router.get("/api/projects/{project_id}/data-points", response_model=DataPointListOut)
async def list_data_points(
    project_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    return await _dp_service(session).list_by_project(project_id, page, page_size)


@router.get("/api/data-points/{dp_id}", response_model=DataPointOut)
async def get_data_point(
    dp_id: int,
    session: AsyncSession = Depends(get_session),
):
    return await _dp_service(session).get(dp_id)


# --- Evidence ---
@router.post("/api/evidences", response_model=EvidenceOut, status_code=status.HTTP_201_CREATED)
async def create_evidence(
    payload: EvidenceCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _ev_service(session).create(payload, ctx)


@router.get("/api/evidences", response_model=EvidenceListOut)
async def list_evidences(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _ev_service(session).list_evidences(ctx, page, page_size)


@router.post("/api/data-points/{dp_id}/evidences")
async def link_evidence_to_dp(
    dp_id: int,
    payload: EvidenceLinkRequest,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _ev_service(session).link_to_data_point(dp_id, payload.evidence_id, ctx)
