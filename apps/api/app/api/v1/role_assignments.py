"""
Role Assignments API — Scoped role management.

Assigns roles to users with specific scopes:
- Company-level roles (editor, reviewer, etc.)
- Report-level roles (auditor for specific report)
- Section-level roles (section_editor/SME for sections)
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import CurrentUser
from app.infra.database import get_session
from app.domain.models import (
    AssignableRole,
    Company,
    CompanyMembership,
    Report,
    RoleAssignment,
    ScopeType,
    Section,
    User,
)
from app.domain.schemas import (
    RoleAssignmentCreate,
    RoleAssignmentDTO,
    RoleAssignmentUpdate,
    RoleAssignmentWithUserDTO,
)

router = APIRouter(prefix="/companies/{company_id}/roles", tags=["role-assignments"])


# =============================================================================
# Role Assignment CRUD
# =============================================================================


@router.get(
    "",
    response_model=list[RoleAssignmentWithUserDTO],
    summary="List role assignments",
)
async def list_assignments(
    company_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[UUID | None, Query(description="Filter by user")] = None,
    scope_type: Annotated[ScopeType | None, Query(description="Filter by scope type")] = None,
    scope_id: Annotated[UUID | None, Query(description="Filter by scope ID")] = None,
    role: Annotated[AssignableRole | None, Query(description="Filter by role")] = None,
) -> list[dict]:
    """List role assignments in company with user info. Requires admin/owner."""
    await _require_company_admin(db, company_id, current_user)

    query = select(RoleAssignment, User).join(
        User, RoleAssignment.user_id == User.user_id
    ).where(
        RoleAssignment.company_id == company_id
    )

    if user_id:
        query = query.where(RoleAssignment.user_id == user_id)
    if scope_type:
        query = query.where(RoleAssignment.scope_type == scope_type)
    if scope_id:
        query = query.where(RoleAssignment.scope_id == scope_id)
    if role:
        query = query.where(RoleAssignment.role == role)

    result = await db.execute(query)

    assignments_with_users = []
    for assignment, user in result.all():
        assignments_with_users.append({
            "assignment_id": assignment.assignment_id,
            "company_id": assignment.company_id,
            "user_id": assignment.user_id,
            "role": assignment.role.value,
            "scope_type": assignment.scope_type.value,
            "scope_id": assignment.scope_id,
            "locales": assignment.locales,
            "created_by": assignment.created_by,
            "created_at_utc": assignment.created_at_utc,
            "user_email": user.email,
            "user_name": user.full_name,
        })

    return assignments_with_users


@router.post(
    "",
    response_model=RoleAssignmentDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Create role assignment",
)
async def create_assignment(
    company_id: UUID,
    data: RoleAssignmentCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> RoleAssignment:
    """
    Create role assignment. Requires admin/owner.

    Validates:
    - User must be a member of the company
    - Scope entity must exist and belong to company
    - No duplicate assignment (same user, role, scope)
    """
    await _require_company_admin(db, company_id, current_user)

    # Validate user is member
    membership = await db.execute(
        select(CompanyMembership).where(
            CompanyMembership.company_id == company_id,
            CompanyMembership.user_id == data.user_id,
            CompanyMembership.is_active == True,  # noqa: E712
        )
    )
    if not membership.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must be a member of the company to receive role assignment",
        )

    # Validate scope entity exists
    await _validate_scope(db, company_id, data.scope_type, data.scope_id)

    # Check for ANY existing roles for this user in this company
    # Business rule: one user can have only ONE role in a company
    existing_roles = await db.execute(
        select(RoleAssignment).where(
            RoleAssignment.company_id == company_id,
            RoleAssignment.user_id == data.user_id,
        )
    )
    existing_assignments = list(existing_roles.scalars().all())

    if existing_assignments:
        # Check if trying to assign the exact same role
        for existing in existing_assignments:
            if (existing.role == data.role and
                existing.scope_type == data.scope_type and
                existing.scope_id == data.scope_id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Role assignment already exists",
                )

        # Delete ALL existing roles (user can have only one role in company)
        for existing in existing_assignments:
            await db.delete(existing)
        await db.flush()

    assignment = RoleAssignment(
        company_id=company_id,
        user_id=data.user_id,
        role=data.role,
        scope_type=data.scope_type,
        scope_id=data.scope_id,
        locales=data.locales,
        created_by=current_user.user_id,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)

    return assignment


@router.get(
    "/{assignment_id}",
    response_model=RoleAssignmentDTO,
    summary="Get role assignment",
)
async def get_assignment(
    company_id: UUID,
    assignment_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> RoleAssignment:
    """Get role assignment by ID. Requires company access."""
    await _require_company_access(db, company_id, current_user)

    result = await db.execute(
        select(RoleAssignment).where(
            RoleAssignment.assignment_id == assignment_id,
            RoleAssignment.company_id == company_id,
        )
    )
    assignment = result.scalar_one_or_none()

    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role assignment not found",
        )

    return assignment


@router.patch(
    "/{assignment_id}",
    response_model=RoleAssignmentDTO,
    summary="Update role assignment",
)
async def update_assignment(
    company_id: UUID,
    assignment_id: UUID,
    data: RoleAssignmentUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> RoleAssignment:
    """Update role assignment. Requires admin/owner."""
    await _require_company_admin(db, company_id, current_user)

    result = await db.execute(
        select(RoleAssignment).where(
            RoleAssignment.assignment_id == assignment_id,
            RoleAssignment.company_id == company_id,
        )
    )
    assignment = result.scalar_one_or_none()

    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role assignment not found",
        )

    # Update fields
    if data.role is not None:
        assignment.role = data.role
    if data.scope_type is not None and data.scope_id is not None:
        await _validate_scope(db, company_id, data.scope_type, data.scope_id)
        assignment.scope_type = data.scope_type
        assignment.scope_id = data.scope_id
    if data.locales is not None:
        assignment.locales = data.locales

    await db.commit()
    await db.refresh(assignment)

    return assignment


@router.delete(
    "/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete role assignment",
)
async def delete_assignment(
    company_id: UUID,
    assignment_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """Delete role assignment. Requires admin/owner."""
    await _require_company_admin(db, company_id, current_user)

    result = await db.execute(
        select(RoleAssignment).where(
            RoleAssignment.assignment_id == assignment_id,
            RoleAssignment.company_id == company_id,
        )
    )
    assignment = result.scalar_one_or_none()

    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role assignment not found",
        )

    await db.delete(assignment)
    await db.commit()


# =============================================================================
# User's Own Roles
# =============================================================================


@router.get(
    "/me",
    response_model=list[RoleAssignmentDTO],
    summary="Get my role assignments",
)
async def get_my_assignments(
    company_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> list[RoleAssignment]:
    """Get current user's role assignments in company."""
    await _require_company_access(db, company_id, current_user)

    result = await db.execute(
        select(RoleAssignment).where(
            RoleAssignment.company_id == company_id,
            RoleAssignment.user_id == current_user.user_id,
        )
    )
    return list(result.scalars().all())


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


async def _require_company_admin(
    db: AsyncSession,
    company_id: UUID,
    user: User,
) -> None:
    """Verify user is company admin or owner."""
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

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this company",
        )

    # Check corporate_lead role
    from app.domain.models import RoleAssignment
    from app.domain.models.enums import AssignableRole, ScopeType
    role_result = await db.execute(
        select(RoleAssignment)
        .where(
            RoleAssignment.user_id == user.user_id,
            RoleAssignment.company_id == company_id,
            RoleAssignment.role == AssignableRole.CORPORATE_LEAD,
            RoleAssignment.scope_type == ScopeType.COMPANY,
            RoleAssignment.scope_id == company_id,
        )
        .limit(1)
    )
    if not role_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires corporate lead role",
        )


async def _validate_scope(
    db: AsyncSession,
    company_id: UUID,
    scope_type: ScopeType,
    scope_id: UUID,
) -> None:
    """Validate scope entity exists and belongs to company."""
    if scope_type == ScopeType.COMPANY:
        if scope_id != company_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Company scope_id must match company_id",
            )

    elif scope_type == ScopeType.REPORT:
        result = await db.execute(
            select(Report).where(
                Report.report_id == scope_id,
                Report.company_id == company_id,
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found or doesn't belong to company",
            )

    elif scope_type == ScopeType.SECTION:
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
                detail="Section not found or doesn't belong to company",
            )

