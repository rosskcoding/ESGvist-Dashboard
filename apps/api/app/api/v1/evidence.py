"""
Evidence API — Audit evidence management.

Manages evidence items (files, links, notes) attached to reports, sections, blocks.

Enhanced workflow fields:
- status (provided/reviewed/issue/resolved)
- sub_anchor_* for granular anchoring
- owner_user_id for assignment
- period_start/period_end for evidence time range
- version_label for tracking
- soft delete (deleted_at/deleted_by)
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import CurrentUser, require_tenant_access
from app.infra.database import get_session
from app.domain.models import (
    Block,
    EvidenceItem,
    EvidenceStatus,
    EvidenceSource,
    EvidenceType,
    EvidenceVisibility,
    LockScopeType,
    Report,
    Section,
)
from app.domain.schemas import EvidenceItemCreate, EvidenceItemDTO, EvidenceItemUpdate, PaginatedResponse

router = APIRouter(prefix="/companies/{company_id}/evidence", tags=["evidence"])


# =============================================================================
# Evidence CRUD
# =============================================================================


@router.get(
    "",
    response_model=PaginatedResponse[EvidenceItemDTO],
    summary="List evidence items",
)
async def list_evidence(
    company_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
    report_id: Annotated[UUID | None, Query(description="Filter by report")] = None,
    scope_type: Annotated[LockScopeType | None, Query(description="Filter by scope type")] = None,
    scope_id: Annotated[UUID | None, Query(description="Filter by scope ID")] = None,
    evidence_type: Annotated[EvidenceType | None, Query(description="Filter by type")] = None,
    visibility: Annotated[EvidenceVisibility | None, Query(description="Filter by visibility")] = None,
    evidence_status: Annotated[EvidenceStatus | None, Query(description="Filter by status", alias="status")] = None,
    owner_user_id: Annotated[UUID | None, Query(description="Filter by owner")] = None,
    include_deleted: Annotated[bool, Query(description="Include soft-deleted items")] = False,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedResponse[EvidenceItemDTO]:
    """List evidence items. Filters by user's visibility access."""
    ctx_report_id: UUID | None = report_id
    ctx_section_id: UUID | None = None

    if scope_type and scope_id:
        resolved_report_id, resolved_section_id = await _resolve_scope_context(
            db, company_id, scope_type, scope_id
        )
        ctx_report_id = ctx_report_id or resolved_report_id
        ctx_section_id = resolved_section_id

    require_tenant_access(
        current_user,
        company_id=company_id,
        permission="evidence:read",
        report_id=ctx_report_id,
        section_id=ctx_section_id,
    )

    query = select(EvidenceItem).where(EvidenceItem.company_id == company_id)

    # By default, exclude soft-deleted items
    if not include_deleted:
        query = query.where(EvidenceItem.deleted_at.is_(None))

    if report_id:
        query = query.where(EvidenceItem.report_id == report_id)
    if scope_type:
        query = query.where(EvidenceItem.scope_type == scope_type)
    if scope_id:
        query = query.where(EvidenceItem.scope_id == scope_id)
    if evidence_type:
        query = query.where(EvidenceItem.type == evidence_type)
    if visibility:
        query = query.where(EvidenceItem.visibility == visibility)
    if evidence_status:
        query = query.where(EvidenceItem.status == evidence_status)
    if owner_user_id:
        query = query.where(EvidenceItem.owner_user_id == owner_user_id)

    # Total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Pagination
    query = query.order_by(EvidenceItem.created_at_utc.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    items = list(result.scalars().all())

    # Filter by visibility access
    # TODO: Implement proper visibility filtering based on user roles
    return PaginatedResponse[EvidenceItemDTO].create(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    response_model=EvidenceItemDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Create evidence item",
)
async def create_evidence(
    company_id: UUID,
    data: EvidenceItemCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> EvidenceItem:
    """Create evidence item. Requires evidence:create permission."""
    ctx_report_id: UUID | None = data.report_id
    ctx_section_id: UUID | None = None

    # Resolve scope_type to LockScopeType for RBAC context
    evidence_scope_type = LockScopeType(data.scope_type)
    _, ctx_section_id = await _resolve_scope_context(
        db, company_id, evidence_scope_type, data.scope_id
    )

    require_tenant_access(
        current_user,
        company_id=company_id,
        permission="evidence:create",
        report_id=ctx_report_id,
        section_id=ctx_section_id,
    )

    # Validate report exists and belongs to company
    report = await db.execute(
        select(Report).where(
            Report.report_id == data.report_id,
            Report.company_id == company_id,
        )
    )
    if not report.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    # Validate scope
    await _validate_evidence_scope(db, company_id, evidence_scope_type, data.scope_id)

    evidence = EvidenceItem(
        company_id=company_id,
        report_id=data.report_id,
        scope_type=evidence_scope_type,
        scope_id=data.scope_id,
        locale=data.locale,
        type=EvidenceType(data.type),
        title=data.title,
        description=data.description,
        tags=data.tags,
        source=EvidenceSource(data.source) if data.source else None,
        visibility=EvidenceVisibility(data.visibility),
        asset_id=data.asset_id,
        url=data.url,
        note_md=data.note_md,
        created_by=current_user.user_id,
        # Workflow fields
        status=EvidenceStatus(data.status),
        sub_anchor_type=data.sub_anchor_type,
        sub_anchor_key=data.sub_anchor_key,
        sub_anchor_label=data.sub_anchor_label,
        owner_user_id=data.owner_user_id,
        period_start=data.period_start,
        period_end=data.period_end,
        version_label=data.version_label,
    )
    db.add(evidence)
    await db.commit()
    await db.refresh(evidence)

    return evidence


@router.get(
    "/{evidence_id}",
    response_model=EvidenceItemDTO,
    summary="Get evidence item",
)
async def get_evidence(
    company_id: UUID,
    evidence_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
    include_deleted: Annotated[bool, Query(description="Include soft-deleted items")] = False,
) -> EvidenceItem:
    """Get evidence item by ID."""
    query = select(EvidenceItem).where(
        EvidenceItem.evidence_id == evidence_id,
        EvidenceItem.company_id == company_id,
    )

    # By default, don't return soft-deleted items
    if not include_deleted:
        query = query.where(EvidenceItem.deleted_at.is_(None))

    result = await db.execute(query)
    evidence = result.scalar_one_or_none()

    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found",
        )

    _, ctx_section_id = await _resolve_scope_context(
        db, company_id, evidence.scope_type, evidence.scope_id
    )
    require_tenant_access(
        current_user,
        company_id=company_id,
        permission="evidence:read",
        report_id=evidence.report_id,
        section_id=ctx_section_id,
    )

    # Check visibility access
    # TODO: Implement visibility check

    return evidence


@router.patch(
    "/{evidence_id}",
    response_model=EvidenceItemDTO,
    summary="Update evidence item",
)
async def update_evidence(
    company_id: UUID,
    evidence_id: UUID,
    data: EvidenceItemUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> EvidenceItem:
    """Update evidence item. Requires evidence:update permission."""
    result = await db.execute(
        select(EvidenceItem).where(
            EvidenceItem.evidence_id == evidence_id,
            EvidenceItem.company_id == company_id,
            EvidenceItem.deleted_at.is_(None),  # Can't update deleted items
        )
    )
    evidence = result.scalar_one_or_none()

    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found",
        )

    # evidence.scope_type is already LockScopeType from model
    _, ctx_section_id = await _resolve_scope_context(
        db, company_id, evidence.scope_type, evidence.scope_id
    )
    require_tenant_access(
        current_user,
        company_id=company_id,
        permission="evidence:update",
        report_id=evidence.report_id,
        section_id=ctx_section_id,
    )

    # Update base fields
    if data.locale is not None:
        evidence.locale = data.locale
    if data.title is not None:
        evidence.title = data.title
    if data.description is not None:
        evidence.description = data.description
    if data.tags is not None:
        evidence.tags = data.tags
    if data.source is not None:
        evidence.source = EvidenceSource(data.source) if data.source else None
    if data.visibility is not None:
        evidence.visibility = EvidenceVisibility(data.visibility)
    if data.url is not None:
        evidence.url = data.url
    if data.note_md is not None:
        evidence.note_md = data.note_md

    # Update workflow fields
    if data.status is not None:
        evidence.status = EvidenceStatus(data.status)
    if data.sub_anchor_type is not None:
        evidence.sub_anchor_type = data.sub_anchor_type
    if data.sub_anchor_key is not None:
        evidence.sub_anchor_key = data.sub_anchor_key
    if data.sub_anchor_label is not None:
        evidence.sub_anchor_label = data.sub_anchor_label
    if data.owner_user_id is not None:
        evidence.owner_user_id = data.owner_user_id
    if data.period_start is not None:
        evidence.period_start = data.period_start
    if data.period_end is not None:
        evidence.period_end = data.period_end
    if data.version_label is not None:
        evidence.version_label = data.version_label

    await db.commit()
    await db.refresh(evidence)

    return evidence


@router.delete(
    "/{evidence_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete evidence item (soft delete)",
)
async def delete_evidence(
    company_id: UUID,
    evidence_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
    hard_delete: Annotated[bool, Query(description="Permanently delete instead of soft delete")] = False,
) -> None:
    """Delete evidence item. Uses soft delete by default (sets deleted_at/deleted_by)."""
    result = await db.execute(
        select(EvidenceItem).where(
            EvidenceItem.evidence_id == evidence_id,
            EvidenceItem.company_id == company_id,
        )
    )
    evidence = result.scalar_one_or_none()

    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found",
        )

    # Already soft-deleted
    if evidence.deleted_at is not None and not hard_delete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found",
        )

    # evidence.scope_type is already LockScopeType from model
    _, ctx_section_id = await _resolve_scope_context(
        db, company_id, evidence.scope_type, evidence.scope_id
    )
    require_tenant_access(
        current_user,
        company_id=company_id,
        permission="evidence:delete",
        report_id=evidence.report_id,
        section_id=ctx_section_id,
    )

    if hard_delete:
        await db.delete(evidence)
    else:
        # Soft delete using model method
        evidence.soft_delete(deleted_by=current_user.user_id)

    await db.commit()


# =============================================================================
# Helpers
# =============================================================================


async def _resolve_scope_context(
    db: AsyncSession,
    company_id: UUID,
    scope_type: LockScopeType,
    scope_id: UUID,
) -> tuple[UUID | None, UUID | None]:
    """
    Resolve evidence scope into (report_id, section_id) for RBAC scoped permissions.
    Returns:
      - report_id: UUID | None
      - section_id: UUID | None
    """
    if scope_type == LockScopeType.REPORT:
        return scope_id, None

    if scope_type == LockScopeType.SECTION:
        result = await db.execute(
            select(Section.report_id)
            .join(Report)
            .where(
                Section.section_id == scope_id,
                Report.company_id == company_id,
            )
        )
        report_id = result.scalar_one_or_none()
        return report_id, scope_id

    if scope_type == LockScopeType.BLOCK:
        result = await db.execute(
            select(Section.section_id, Section.report_id)
            .select_from(Block)
            .join(Section, Block.section_id == Section.section_id)
            .join(Report, Section.report_id == Report.report_id)
            .where(
                Block.block_id == scope_id,
                Report.company_id == company_id,
            )
        )
        row = result.one_or_none()
        if not row:
            return None, None
        section_id, report_id = row
        return report_id, section_id

    # Company or unknown scope: can't provide narrower context.
    return None, None


async def _validate_evidence_scope(
    db: AsyncSession,
    company_id: UUID,
    scope_type: LockScopeType,
    scope_id: UUID,
) -> None:
    """Validate scope entity exists and belongs to company."""
    if scope_type == LockScopeType.REPORT:
        result = await db.execute(
            select(Report).where(
                Report.report_id == scope_id,
                Report.company_id == company_id,
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found",
            )

    elif scope_type == LockScopeType.SECTION:
        result = await db.execute(
            select(Section)
            .join(Report)
            .where(
                Section.section_id == scope_id,
                Report.company_id == company_id,
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Section not found",
            )

    elif scope_type == LockScopeType.BLOCK:
        result = await db.execute(
            select(Block)
            .join(Section)
            .join(Report)
            .where(
                Block.block_id == scope_id,
                Report.company_id == company_id,
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Block not found",
            )
