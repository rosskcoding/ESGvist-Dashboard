"""
Companies API — Multi-tenant company management.

Platform-level operations:
- Create/list/update companies (superuser only)
- Manage company status

Company-level operations:
- Get company details
- Manage members (owner/admin)
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import CurrentUser
from app.domain.models import Company, CompanyMembership, CompanyStatus, RoleAssignment, User
from app.domain.models.company import generate_slug
from app.domain.models.enums import AssignableRole, ScopeType
from app.domain.schemas import (
    CompanyCreate,
    CompanyDTO,
    CompanyUpdate,
    MembershipDTO,
    MembershipInvite,
    MembershipUpdate,
    MembershipWithUserDTO,
    UserCreate,
)
from app.infra.database import get_session
from app.services.audit_logger import AuditLogger
from app.services.auth import hash_password

router = APIRouter(prefix="/companies", tags=["companies"])


# =============================================================================
# Helper functions
# =============================================================================


async def _get_company_by_slug_or_id(
    session: AsyncSession,
    identifier: str,
) -> Company:
    """
    Get company by slug or UUID.

    Args:
        session: Database session
        identifier: Company slug or UUID

    Returns:
        Company instance

    Raises:
        HTTPException: If company not found
    """
    # Try to parse as UUID
    try:
        company_uuid = UUID(identifier)
        result = await session.execute(
            select(Company).where(Company.company_id == company_uuid)
        )
    except ValueError:
        # Not a valid UUID, treat as slug
        result = await session.execute(
            select(Company).where(Company.slug == identifier)
        )

    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company '{identifier}' not found",
        )

    return company


async def _check_corporate_lead(
    session: AsyncSession,
    user_id: UUID,
    company_id: UUID,
) -> bool:
    """Check if user has corporate_lead role in company."""
    result = await session.execute(
        select(RoleAssignment)
        .where(
            RoleAssignment.user_id == user_id,
            RoleAssignment.company_id == company_id,
            RoleAssignment.role == AssignableRole.CORPORATE_LEAD,
            RoleAssignment.scope_type == ScopeType.COMPANY,
            RoleAssignment.scope_id == company_id,
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


# =============================================================================
# Platform-level: Company CRUD (superuser only)
# =============================================================================


@router.post(
    "",
    response_model=CompanyDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Create company (platform admin)",
)
async def create_company(
    data: CompanyCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> Company:
    """Create a new company. Requires platform admin (superuser)."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only platform admins can create companies",
        )

    # Check name uniqueness
    existing = await db.execute(
        select(Company).where(Company.name == data.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Company with name '{data.name}' already exists",
        )

    # Generate unique slug
    base_slug = generate_slug(data.name)
    slug = base_slug
    counter = 1

    while True:
        existing_slug = await db.execute(
            select(Company).where(Company.slug == slug)
        )
        if not existing_slug.scalar_one_or_none():
            break
        slug = f"{base_slug}-{counter}"
        counter += 1

    company = Company(
        name=data.name,
        slug=slug,
        status=CompanyStatus.ACTIVE,
        created_by=current_user.user_id,
    )
    db.add(company)
    await db.flush()

    # Auto-create membership for creator
    membership = CompanyMembership(
        company_id=company.company_id,
        user_id=current_user.user_id,
        is_active=True,
        created_by=current_user.user_id,
    )
    db.add(membership)
    await db.flush()

    # Auto-assign corporate_lead role to creator
    role_assignment = RoleAssignment(
        company_id=company.company_id,
        user_id=current_user.user_id,
        role=AssignableRole.CORPORATE_LEAD,
        scope_type=ScopeType.COMPANY,
        scope_id=company.company_id,
        created_by=current_user.user_id,
    )
    db.add(role_assignment)
    await db.flush()

    # Audit log
    audit_logger = AuditLogger(db)
    await audit_logger.log_company_create(
        actor=current_user,
        company_id=company.company_id,
        company_name=company.name,
    )

    await db.commit()
    await db.refresh(company)

    return company


@router.get(
    "",
    response_model=list[CompanyDTO],
    summary="List companies (platform admin) or user's companies",
)
async def list_companies(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> list[Company]:
    """
    List companies.

    - Platform admins see all companies
    - Regular users see only companies they're members of
    """
    if current_user.is_superuser:
        result = await db.execute(select(Company))
        return list(result.scalars().all())

    # Get user's companies via membership
    result = await db.execute(
        select(Company)
        .join(CompanyMembership)
        .where(
            CompanyMembership.user_id == current_user.user_id,
            CompanyMembership.is_active == True,  # noqa: E712
        )
    )
    return list(result.scalars().all())


@router.get(
    "/{company_identifier}",
    response_model=CompanyDTO,
    summary="Get company details",
)
async def get_company(
    company_identifier: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> Company:
    """Get company by slug or UUID. Requires membership or platform admin."""
    company = await _get_company_by_slug_or_id(db, company_identifier)

    # Check access
    if not current_user.is_superuser:
        membership = await db.execute(
            select(CompanyMembership).where(
                CompanyMembership.company_id == company.company_id,
                CompanyMembership.user_id == current_user.user_id,
                CompanyMembership.is_active == True,  # noqa: E712
            )
        )
        if not membership.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No access to this company",
            )

    return company


@router.patch(
    "/{company_identifier}",
    response_model=CompanyDTO,
    summary="Update company (platform admin or owner)",
)
async def update_company(
    company_identifier: str,
    data: CompanyUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> Company:
    """Update company. Requires platform admin or company owner."""
    company = await _get_company_by_slug_or_id(db, company_identifier)

    # Check permissions
    can_update = current_user.is_superuser
    if not can_update:
        can_update = await _check_corporate_lead(db, current_user.user_id, company.company_id)

    if not can_update:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only platform admins or corporate leads can update company",
        )

    # Update fields
    if data.name is not None:
        # Check uniqueness
        existing = await db.execute(
            select(Company).where(
                Company.name == data.name,
                Company.company_id != company.company_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Company with name '{data.name}' already exists",
            )
        company.name = data.name

        # Regenerate slug if name changes
        base_slug = generate_slug(data.name)
        slug = base_slug
        counter = 1

        while True:
            existing_slug = await db.execute(
                select(Company).where(
                    Company.slug == slug,
                    Company.company_id != company.company_id,
                )
            )
            if not existing_slug.scalar_one_or_none():
                break
            slug = f"{base_slug}-{counter}"
            counter += 1

        company.slug = slug

    if data.status is not None:
        company.status = CompanyStatus(data.status)

    await db.commit()
    await db.refresh(company)

    return company


@router.delete(
    "/{company_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete company (platform admin only)",
)
async def delete_company(
    company_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """Delete a company. Requires platform admin (superuser)."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only platform admins can delete companies",
        )

    result = await db.execute(
        select(Company).where(Company.company_id == company_id)
    )
    company = result.scalar_one_or_none()

    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    company_name = company.name

    # Delete all role assignments for this company
    await db.execute(
        RoleAssignment.__table__.delete().where(
            RoleAssignment.company_id == company_id
        )
    )

    # Delete all memberships
    await db.execute(
        CompanyMembership.__table__.delete().where(
            CompanyMembership.company_id == company_id
        )
    )

    # Delete company
    await db.delete(company)

    # Audit log
    audit_logger = AuditLogger(db)
    await audit_logger.log_company_delete(
        actor=current_user,
        company_id=company_id,
        company_name=company_name,
    )

    await db.commit()


# =============================================================================
# Company Members Management
# =============================================================================


@router.get(
    "/{company_identifier}/members",
    response_model=list[MembershipWithUserDTO],
    summary="List company members",
)
async def list_members(
    company_identifier: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict]:
    """List company members with user info. Requires membership."""
    # Get company by slug or ID
    company = await _get_company_by_slug_or_id(db, company_identifier)

    # Verify user has access
    await _require_company_access(db, company.company_id, current_user)

    result = await db.execute(
        select(CompanyMembership, User)
        .join(User, CompanyMembership.user_id == User.user_id)
        .where(CompanyMembership.company_id == company.company_id)
    )

    memberships_with_users = []
    for membership, user in result.all():
        is_corporate_lead = await _check_corporate_lead(db, user.user_id, company.company_id)
        memberships_with_users.append({
            "membership_id": membership.membership_id,
            "company_id": membership.company_id,
            "user_id": membership.user_id,
            "is_active": membership.is_active,
            "created_by": membership.created_by,
            "created_at_utc": membership.created_at_utc,
            "updated_at_utc": membership.updated_at_utc,
            "user_email": user.email,
            "user_name": user.full_name,
            "is_corporate_lead": is_corporate_lead,
        })

    return memberships_with_users


@router.post(
    "/{company_identifier}/members",
    response_model=MembershipDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Add member to company",
)
async def add_member(
    company_identifier: str,
    data: MembershipInvite,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> CompanyMembership:
    """Add user to company. Requires owner/admin."""
    company = await _get_company_by_slug_or_id(db, company_identifier)
    await _require_company_admin(db, company.company_id, current_user)

    # Check user exists
    user_result = await db.execute(
        select(User).where(User.user_id == data.user_id)
    )
    if not user_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Check not already member
    existing = await db.execute(
        select(CompanyMembership).where(
            CompanyMembership.company_id == company.company_id,
            CompanyMembership.user_id == data.user_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this company",
        )

    membership = CompanyMembership(
        company_id=company.company_id,
        user_id=data.user_id,
        is_active=True,
        created_by=current_user.user_id,
    )
    db.add(membership)
    await db.flush()

    # Audit log
    audit_logger = AuditLogger(db)
    await audit_logger.log_member_invite(
        actor=current_user,
        company_id=company.company_id,
        user_id=data.user_id,
    )

    await db.commit()
    await db.refresh(membership)

    return membership


@router.post(
    "/{company_identifier}/members/create-and-add",
    response_model=MembershipDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Create new user and add to company",
)
async def create_and_add_member(
    company_identifier: str,
    data: UserCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> CompanyMembership:
    """
    Create a new user and add them to the company.
    Requires corporate_lead role.

    This endpoint allows Corporate Leads to create new users
    who are automatically added to their company.
    """
    company = await _get_company_by_slug_or_id(db, company_identifier)
    await _require_company_admin(db, company.company_id, current_user)

    # Check email uniqueness
    existing_user = await db.execute(
        select(User).where(User.email == data.email)
    )
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email '{data.email}' already exists",
        )

    # Create new user (NOT a superuser)
    new_user = User(
        email=data.email,
        full_name=data.full_name,
        password_hash=hash_password(data.password),
        is_superuser=False,  # Corporate Lead cannot create superusers
        is_active=True,
    )
    db.add(new_user)
    await db.flush()

    # Add user to company
    membership = CompanyMembership(
        company_id=company.company_id,
        user_id=new_user.user_id,
        is_active=True,
        created_by=current_user.user_id,
    )
    db.add(membership)
    await db.flush()

    # Audit log
    audit_logger = AuditLogger(db)
    await audit_logger.log_member_invite(
        actor=current_user,
        company_id=company.company_id,
        user_id=new_user.user_id,
    )

    await db.commit()
    await db.refresh(membership)

    return membership


@router.patch(
    "/{company_identifier}/members/{user_id}",
    response_model=MembershipDTO,
    summary="Update member",
)
async def update_member(
    company_identifier: str,
    user_id: UUID,
    data: MembershipUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> CompanyMembership:
    """
    Update member's info. Requires corporate_lead.

    Corporate Lead can update:
    - Member's full name
    - Member's active status
    """
    company = await _get_company_by_slug_or_id(db, company_identifier)
    await _require_company_admin(db, company.company_id, current_user)

    # Get membership
    result = await db.execute(
        select(CompanyMembership).where(
            CompanyMembership.company_id == company.company_id,
            CompanyMembership.user_id == user_id,
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found",
        )

    # Update membership status if provided
    if data.is_active is not None:
        membership.is_active = data.is_active

    # Update user's full name if provided
    if data.full_name is not None:
        user_result = await db.execute(
            select(User).where(User.user_id == user_id)
        )
        user = user_result.scalar_one_or_none()
        if user:
            user.full_name = data.full_name

    await db.commit()
    await db.refresh(membership)

    return membership


@router.delete(
    "/{company_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove member from company",
)
async def remove_member(
    company_id: UUID,
    user_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """Remove member from company. Requires owner/admin."""
    await _require_company_admin(db, company_id, current_user)

    result = await db.execute(
        select(CompanyMembership).where(
            CompanyMembership.company_id == company_id,
            CompanyMembership.user_id == user_id,
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found",
        )

    # Prevent removing last corporate_lead
    is_corporate_lead = await _check_corporate_lead(db, user_id, company_id)
    if is_corporate_lead:
        corporate_lead_count = await db.execute(
            select(RoleAssignment)
            .where(
                RoleAssignment.company_id == company_id,
                RoleAssignment.role == AssignableRole.CORPORATE_LEAD,
                RoleAssignment.scope_type == ScopeType.COMPANY,
                RoleAssignment.scope_id == company_id,
            )
        )
        if len(list(corporate_lead_count.scalars().all())) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the last corporate lead",
            )

    await db.delete(membership)
    await db.commit()


# =============================================================================
# Helpers
# =============================================================================


async def _require_company_access(
    db: AsyncSession,
    company_id: UUID,
    user: User,
) -> CompanyMembership | None:
    """Verify user has access to company."""
    if user.is_superuser:
        return None

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

    return membership


async def _require_company_admin(
    db: AsyncSession,
    company_id: UUID,
    user: User,
) -> CompanyMembership | None:
    """Verify user is corporate_lead."""
    if user.is_superuser:
        return None

    # Check membership exists
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
    if not await _check_corporate_lead(db, user.user_id, company_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires corporate lead role",
        )

    return membership


async def _require_company_owner(
    db: AsyncSession,
    company_id: UUID,
    user: User,
) -> CompanyMembership | None:
    """Verify user is corporate_lead (alias for _require_company_admin)."""
    return await _require_company_admin(db, company_id, user)

