from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.core.exceptions import AppError
from app.db.models.data_point import DataPoint
from app.db.models.evidence import DataPointEvidence, Evidence
from app.db.models.requirement_item_evidence import RequirementItemEvidence
from app.db.session import get_session
from app.policies.auth_policy import AuthPolicy
from app.policies.evidence_policy import EvidencePolicy
from app.repositories.audit_repo import AuditRepository
from app.repositories.data_point_repo import DataPointRepository
from app.repositories.evidence_repo import EvidenceRepository
from app.repositories.project_repo import ProjectRepository
from app.schemas.data_points import DataPointCreate, DataPointListOut, DataPointOut
from app.schemas.evidence import (
    EvidenceCreate,
    EvidenceLinkRequest,
    EvidenceListOut,
    EvidenceOut,
)
from app.services.data_point_service import DataPointService
from app.services.evidence_service import EvidenceService

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/csv",
    "image/png",
    "image/jpeg",
}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

router = APIRouter(tags=["Data Points & Evidence"])


def _dp_service(session: AsyncSession) -> DataPointService:
    return DataPointService(
        repo=DataPointRepository(session),
        project_repo=ProjectRepository(session),
        audit_repo=AuditRepository(session),
    )


def _ev_service(session: AsyncSession) -> EvidenceService:
    return EvidenceService(
        repo=EvidenceRepository(session),
        dp_repo=DataPointRepository(session),
        project_repo=ProjectRepository(session),
        audit_repo=AuditRepository(session),
    )


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
    AuthPolicy.require_write_access(ctx)
    return await _dp_service(session).create(project_id, payload, ctx)


@router.get("/api/projects/{project_id}/data-points", response_model=DataPointListOut)
async def list_data_points(
    project_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _dp_service(session).list_by_project(project_id, ctx, page, page_size)


@router.get("/api/data-points/{dp_id}", response_model=DataPointOut)
async def get_data_point(
    dp_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _dp_service(session).get(dp_id, ctx)


# --- Evidence ---
@router.post("/api/evidences", response_model=EvidenceOut, status_code=status.HTTP_201_CREATED)
async def create_evidence(
    payload: EvidenceCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.require_write_access(ctx)

    # File size / mime type validation for file-type evidence
    if payload.type == "file":
        if payload.file_size and payload.file_size > MAX_FILE_SIZE:
            raise AppError(
                "FILE_TOO_LARGE", 422,
                f"File size {payload.file_size} exceeds maximum of {MAX_FILE_SIZE} bytes (50MB)"
            )
        if payload.mime_type and payload.mime_type not in ALLOWED_MIME_TYPES:
            raise AppError(
                "INVALID_MIME_TYPE", 422,
                f"MIME type '{payload.mime_type}' is not allowed. "
                f"Allowed types: pdf, xlsx, docx, csv, png, jpg"
            )

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
    AuthPolicy.require_write_access(ctx)
    return await _ev_service(session).link_to_data_point(dp_id, payload.evidence_id, ctx)


# --- Evidence: bind to requirement item ---
class RequirementItemBindRequest(BaseModel):
    requirement_item_id: int


@router.post("/api/evidence/{evidence_id}/bind-requirement")
async def bind_evidence_to_requirement(
    evidence_id: int,
    payload: RequirementItemBindRequest,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.require_write_access(ctx)

    # Verify evidence exists
    repo = EvidenceRepository(session)
    await repo.get_or_raise(evidence_id)

    # Check for existing binding (dedup)
    existing = await session.execute(
        select(RequirementItemEvidence).where(
            RequirementItemEvidence.requirement_item_id == payload.requirement_item_id,
            RequirementItemEvidence.evidence_id == evidence_id,
        )
    )
    if existing.scalar_one_or_none():
        raise AppError("ALREADY_LINKED", 409, "Evidence already linked to this requirement item")

    binding = RequirementItemEvidence(
        requirement_item_id=payload.requirement_item_id,
        evidence_id=evidence_id,
        linked_by=ctx.user_id,
    )
    session.add(binding)
    await session.flush()
    return {
        "evidence_id": evidence_id,
        "requirement_item_id": payload.requirement_item_id,
        "linked": True,
    }


# --- Evidence: delete with protection ---
@router.delete("/api/evidence/{evidence_id}", status_code=status.HTTP_200_OK)
async def delete_evidence(
    evidence_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.require_write_access(ctx)

    repo = EvidenceRepository(session)
    ev = await repo.get_or_raise(evidence_id)

    policy = EvidencePolicy()
    policy.can_delete(ctx, ev.created_by)
    await policy.not_in_approved_scope(repo, evidence_id)

    await session.delete(ev)
    await session.flush()
    return {"id": evidence_id, "deleted": True}
