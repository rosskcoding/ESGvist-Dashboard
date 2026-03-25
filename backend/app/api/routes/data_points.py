from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.core.exceptions import AppError
from app.db.session import get_session
from app.policies.auth_policy import AuthPolicy
from app.policies.evidence_policy import EvidencePolicy
from app.repositories.audit_repo import AuditRepository
from app.repositories.data_point_repo import DataPointRepository
from app.repositories.evidence_repo import EvidenceRepository
from app.repositories.project_repo import ProjectRepository
from app.schemas.data_points import (
    DataPointCreate,
    DataPointListOut,
    DataPointOut,
    DataPointUpdate,
)
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
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

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


@router.patch("/api/data-points/{dp_id}", response_model=DataPointOut)
async def update_data_point(
    dp_id: int,
    payload: DataPointUpdate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.require_write_access(ctx)
    return await _dp_service(session).update(dp_id, payload, ctx)


# --- Version History ---
@router.get("/api/data-points/{dp_id}/versions")
async def list_data_point_versions(
    dp_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    """Return the immutable version history for a data point.

    Accessible to any user who can view the data point (collector for own,
    reviewer for assigned, admin/esg_manager/auditor for project scope).
    """
    from app.core.access import get_data_point_for_ctx
    from app.repositories.data_point_repo import DataPointRepository

    await get_data_point_for_ctx(session, dp_id, ctx)
    versions = await DataPointRepository(session).list_versions(dp_id)
    return [
        {
            "id": v.id,
            "data_point_id": v.data_point_id,
            "version": v.version,
            "numeric_value": float(v.numeric_value) if v.numeric_value is not None else None,
            "text_value": v.text_value,
            "unit_code": v.unit_code,
            "status": v.status,
            "changed_by": v.changed_by,
            "change_reason": v.change_reason,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in versions
    ]


# --- Evidence ---
@router.post("/api/evidences", response_model=EvidenceOut, status_code=status.HTTP_201_CREATED)
async def create_evidence(
    payload: EvidenceCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    # File size / mime type validation for file-type evidence
    if payload.type == "file":
        if payload.file_size and payload.file_size > MAX_FILE_SIZE:
            raise AppError(
                "FILE_TOO_LARGE", 422,
                f"File size {payload.file_size} exceeds maximum of {MAX_FILE_SIZE} bytes (10MB)"
            )
        if payload.mime_type and payload.mime_type not in ALLOWED_MIME_TYPES:
            raise AppError(
                "INVALID_MIME_TYPE", 422,
                f"MIME type '{payload.mime_type}' is not allowed. "
                f"Allowed types: pdf, xlsx, docx, csv, png, jpg"
            )

    return await _ev_service(session).create(payload, ctx)


@router.post("/api/evidences/upload", response_model=EvidenceOut, status_code=status.HTTP_201_CREATED)
async def upload_evidence(
    file: UploadFile = File(...),
    title: str = Form(...),
    description: str = Form(""),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    if not file.content_type or file.content_type not in ALLOWED_MIME_TYPES:
        raise AppError(
            "INVALID_MIME_TYPE", 422,
            f"MIME type '{file.content_type}' is not allowed. "
            f"Allowed types: pdf, xlsx, docx, csv, png, jpg"
        )
    file_data = await file.read()
    if len(file_data) > MAX_FILE_SIZE:
        raise AppError(
            "FILE_TOO_LARGE", 422,
            f"File size {len(file_data)} exceeds maximum of {MAX_FILE_SIZE} bytes (10MB)"
        )
    return await _ev_service(session).create_with_file(
        file_data=file_data,
        file_name=file.filename or "unnamed",
        mime_type=file.content_type,
        title=title,
        description=description or None,
        ctx=ctx,
    )


@router.get("/api/evidences/{evidence_id}/download")
async def download_evidence(
    evidence_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    url = await _ev_service(session).get_download_url(evidence_id, ctx)
    return RedirectResponse(url=url)


@router.get("/api/evidences", response_model=EvidenceListOut)
async def list_evidences(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    unlinked: bool | None = None,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.require_role(ctx, ["admin", "platform_admin", "esg_manager", "collector", "auditor"])
    return await _ev_service(session).list_evidences(ctx, page, page_size, unlinked=unlinked)


@router.get("/api/evidences/{evidence_id}", response_model=EvidenceOut)
async def get_evidence(
    evidence_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _ev_service(session).get_evidence(evidence_id, ctx)


class EvidenceUpdate(BaseModel):
    title: str | None = None
    description: str | None = None


@router.put("/api/evidences/{evidence_id}", response_model=EvidenceOut)
async def update_evidence(
    evidence_id: int,
    payload: EvidenceUpdate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _ev_service(session).update_evidence(
        evidence_id, payload.model_dump(exclude_unset=True), ctx
    )


@router.post("/api/data-points/{dp_id}/evidences")
async def link_evidence_to_dp(
    dp_id: int,
    payload: EvidenceLinkRequest,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _ev_service(session).link_to_data_point(dp_id, payload.evidence_id, ctx)


@router.delete("/api/data-points/{dp_id}/evidences/{evidence_id}")
async def unlink_evidence_from_dp(
    dp_id: int,
    evidence_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _ev_service(session).unlink_from_data_point(dp_id, evidence_id, ctx)


@router.get("/api/data-points/{dp_id}/evidences")
async def list_evidence_for_dp(
    dp_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _ev_service(session).list_for_data_point(dp_id, ctx)


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
    return await _ev_service(session).bind_to_requirement(
        evidence_id,
        payload.requirement_item_id,
        ctx,
    )


# --- Evidence: scanning suggestions ---
@router.get("/api/evidences/{evidence_id}/suggestions")
async def get_evidence_suggestions(
    evidence_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    """Return AI-powered suggestions for the evidence (file type, quality, linking).

    Phase 3 feature — currently returns rule-based suggestions.
    """
    return await _ev_service(session).get_suggestions(evidence_id, ctx)


# --- Evidence: delete with protection ---
@router.delete("/api/evidence/{evidence_id}", status_code=status.HTTP_200_OK)
async def delete_evidence(
    evidence_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    repo = EvidenceRepository(session)
    ev = await repo.get_or_raise(evidence_id)
    if ev.organization_id != ctx.organization_id and not ctx.is_platform_admin:
        raise AppError("FORBIDDEN", 403, "Evidence belongs to another organization")

    policy = EvidencePolicy()
    policy.can_delete(ctx, ev.created_by)
    await policy.not_in_approved_scope(repo, evidence_id)

    await session.delete(ev)
    await session.flush()
    return {"id": evidence_id, "deleted": True}
