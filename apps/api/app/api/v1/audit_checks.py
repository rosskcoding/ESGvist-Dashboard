"""
Audit Checks API — Audit checklist management.

Manages audit check marks on reports, sections, blocks, and evidence items.
"""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import CurrentUser
from app.infra.database import get_session
from app.domain.models import (
    AuditCheck,
    AuditCheckSeverity,
    AuditCheckStatus,
    AuditCheckTargetType,
    Block,
    CompanyMembership,
    EvidenceItem,
    Report,
    Section,
    SourceSnapshot,
    User,
)
from app.domain.schemas import AuditCheckCreate, AuditCheckDTO, AuditCheckUpdate

router = APIRouter(prefix="/companies/{company_id}/audit-checks", tags=["audit-checks"])


# =============================================================================
# Audit Check CRUD
# =============================================================================


@router.get(
    "",
    response_model=list[AuditCheckDTO],
    summary="List audit checks",
)
async def list_checks(
    company_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
    report_id: Annotated[UUID | None, Query(description="Filter by report")] = None,
    target_type: Annotated[AuditCheckTargetType | None, Query(description="Filter by target type")] = None,
    target_id: Annotated[UUID | None, Query(description="Filter by target ID")] = None,
    check_status: Annotated[AuditCheckStatus | None, Query(description="Filter by status")] = None,
    auditor_id: Annotated[UUID | None, Query(description="Filter by auditor")] = None,
) -> list[AuditCheck]:
    """List audit checks. Requires company access."""
    await _require_company_access(db, company_id, current_user)

    query = select(AuditCheck).where(AuditCheck.company_id == company_id)

    if report_id:
        query = query.where(AuditCheck.report_id == report_id)
    if target_type:
        query = query.where(AuditCheck.target_type == target_type)
    if target_id:
        query = query.where(AuditCheck.target_id == target_id)
    if check_status:
        query = query.where(AuditCheck.status == check_status)
    if auditor_id:
        query = query.where(AuditCheck.auditor_id == auditor_id)

    result = await db.execute(query)
    return list(result.scalars().all())


@router.post(
    "",
    response_model=AuditCheckDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Create audit check",
)
async def create_check(
    company_id: UUID,
    data: AuditCheckCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> AuditCheck:
    """Create audit check. Requires audit_check:update permission."""
    await _require_auditor_access(db, company_id, current_user)

    # Validate report
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

    # Validate snapshot if provided
    if data.source_snapshot_id:
        snapshot = await db.execute(
            select(SourceSnapshot).where(
                SourceSnapshot.snapshot_id == data.source_snapshot_id,
                SourceSnapshot.report_id == data.report_id,
            )
        )
        if not snapshot.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Snapshot not found",
            )

    # Validate target
    await _validate_audit_target(
        db, company_id, data.report_id, data.target_type, data.target_id
    )

    check = AuditCheck(
        company_id=company_id,
        report_id=data.report_id,
        source_snapshot_id=data.source_snapshot_id,
        target_type=data.target_type,
        target_id=data.target_id,
        auditor_id=current_user.user_id,
        status=data.status,
        severity=data.severity,
        comment=data.comment,
        reviewed_at=datetime.now(UTC) if data.status != AuditCheckStatus.NOT_STARTED else None,
    )
    db.add(check)
    await db.commit()
    await db.refresh(check)

    return check


@router.get(
    "/{check_id}",
    response_model=AuditCheckDTO,
    summary="Get audit check",
)
async def get_check(
    company_id: UUID,
    check_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> AuditCheck:
    """Get audit check by ID."""
    await _require_company_access(db, company_id, current_user)

    result = await db.execute(
        select(AuditCheck).where(
            AuditCheck.check_id == check_id,
            AuditCheck.company_id == company_id,
        )
    )
    check = result.scalar_one_or_none()

    if not check:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit check not found",
        )

    return check


@router.patch(
    "/{check_id}",
    response_model=AuditCheckDTO,
    summary="Update audit check",
)
async def update_check(
    company_id: UUID,
    check_id: UUID,
    data: AuditCheckUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> AuditCheck:
    """Update audit check. Only auditor who created or audit lead can update."""
    result = await db.execute(
        select(AuditCheck).where(
            AuditCheck.check_id == check_id,
            AuditCheck.company_id == company_id,
        )
    )
    check = result.scalar_one_or_none()

    if not check:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit check not found",
        )

    # Check permission: own check or audit lead
    is_own_check = check.auditor_id == current_user.user_id
    is_audit_lead = await _is_audit_lead(db, company_id, current_user)

    if not is_own_check and not is_audit_lead and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only update own audit checks or requires audit lead permission",
        )

    # Update fields
    if data.status is not None:
        check.status = data.status
        check.reviewed_at = datetime.now(UTC)
    if data.severity is not None:
        check.severity = data.severity
    if data.comment is not None:
        check.comment = data.comment

    await db.commit()
    await db.refresh(check)

    return check


@router.delete(
    "/{check_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete audit check",
)
async def delete_check(
    company_id: UUID,
    check_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """Delete audit check. Requires audit lead permission."""
    await _require_audit_lead(db, company_id, current_user)

    result = await db.execute(
        select(AuditCheck).where(
            AuditCheck.check_id == check_id,
            AuditCheck.company_id == company_id,
        )
    )
    check = result.scalar_one_or_none()

    if not check:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit check not found",
        )

    await db.delete(check)
    await db.commit()


# =============================================================================
# Audit Summary
# =============================================================================


@router.get(
    "/summary/{report_id}",
    summary="Get audit summary for report",
)
async def get_audit_summary(
    company_id: UUID,
    report_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """
    Get audit summary for a report.

    Returns:
    - total_checks: Total number of audit checks
    - by_status: Counts by status
    - by_severity: Counts by severity (for flagged items)
    - coverage: Percentage of audited items
    """
    await _require_company_access(db, company_id, current_user)

    # Validate report
    report = await db.execute(
        select(Report).where(
            Report.report_id == report_id,
            Report.company_id == company_id,
        )
    )
    if not report.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    # Get all checks for report
    result = await db.execute(
        select(AuditCheck).where(
            AuditCheck.report_id == report_id,
            AuditCheck.company_id == company_id,
        )
    )
    checks = list(result.scalars().all())

    # Calculate summary
    total = len(checks)
    by_status = {}
    by_severity = {}

    for check in checks:
        # Status counts
        status_key = check.status.value
        by_status[status_key] = by_status.get(status_key, 0) + 1

        # Severity counts (only for flagged)
        if check.status == AuditCheckStatus.FLAGGED and check.severity:
            sev_key = check.severity.value
            by_severity[sev_key] = by_severity.get(sev_key, 0) + 1

    reviewed_count = sum(
        count for status, count in by_status.items()
        if status in ["reviewed", "flagged"]
    )
    coverage = (reviewed_count / total * 100) if total > 0 else 0

    return {
        "total_checks": total,
        "by_status": by_status,
        "by_severity": by_severity,
        "coverage_percent": round(coverage, 1),
        "has_critical_issues": by_severity.get("critical", 0) > 0,
        "has_major_issues": by_severity.get("major", 0) > 0,
    }


# =============================================================================
# Helpers
# =============================================================================


async def _require_company_access(
    db: AsyncSession,
    company_id: UUID,
    user: User,
) -> None:
    """Verify user has access to company."""
    if user.is_superuser:
        return

    result = await db.execute(
        select(CompanyMembership).where(
            CompanyMembership.company_id == company_id,
            CompanyMembership.user_id == user.user_id,
            CompanyMembership.is_active == True,  # noqa: E712
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this company",
        )


async def _require_auditor_access(
    db: AsyncSession,
    company_id: UUID,
    user: User,
) -> None:
    """Verify user has auditor or audit lead role."""
    if user.is_superuser:
        return

    # Check membership
    result = await db.execute(
        select(CompanyMembership).where(
            CompanyMembership.company_id == company_id,
            CompanyMembership.user_id == user.user_id,
            CompanyMembership.is_active == True,  # noqa: E712
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this company",
        )

    # Owner/admin can audit
    if membership.is_owner or membership.is_admin:
        return

    # TODO: Check for auditor or audit_lead role assignment
    # For now, allow any member
    return


async def _require_audit_lead(
    db: AsyncSession,
    company_id: UUID,
    user: User,
) -> None:
    """Verify user has audit lead role."""
    if user.is_superuser:
        return

    result = await db.execute(
        select(CompanyMembership).where(
            CompanyMembership.company_id == company_id,
            CompanyMembership.user_id == user.user_id,
            CompanyMembership.is_active == True,  # noqa: E712
        )
    )
    membership = result.scalar_one_or_none()

    if not membership or not membership.is_owner:
        # TODO: Check for audit_lead role assignment
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires audit lead permission",
        )


async def _is_audit_lead(
    db: AsyncSession,
    company_id: UUID,
    user: User,
) -> bool:
    """Check if user is audit lead."""
    if user.is_superuser:
        return True

    result = await db.execute(
        select(CompanyMembership).where(
            CompanyMembership.company_id == company_id,
            CompanyMembership.user_id == user.user_id,
            CompanyMembership.is_active == True,  # noqa: E712
        )
    )
    membership = result.scalar_one_or_none()

    # Owner is considered audit lead
    return membership is not None and membership.is_owner


async def _validate_audit_target(
    db: AsyncSession,
    company_id: UUID,
    report_id: UUID,
    target_type: AuditCheckTargetType,
    target_id: UUID,
) -> None:
    """Validate audit target exists and belongs to report."""
    if target_type == AuditCheckTargetType.REPORT:
        if target_id != report_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Report target_id must match report_id",
            )

    elif target_type == AuditCheckTargetType.SECTION:
        result = await db.execute(
            select(Section).where(
                Section.section_id == target_id,
                Section.report_id == report_id,
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Section not found in report",
            )

    elif target_type == AuditCheckTargetType.BLOCK:
        result = await db.execute(
            select(Block)
            .join(Section)
            .where(
                Block.block_id == target_id,
                Section.report_id == report_id,
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Block not found in report",
            )

    elif target_type == AuditCheckTargetType.EVIDENCE_ITEM:
        result = await db.execute(
            select(EvidenceItem).where(
                EvidenceItem.evidence_id == target_id,
                EvidenceItem.report_id == report_id,
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evidence item not found in report",
            )

