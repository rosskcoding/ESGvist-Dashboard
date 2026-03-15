"""
Development seed data: dev/e2e users.

This module is ONLY intended for development environments (DEBUG / environment=development).
It ensures that the documented E2E user exists so Playwright tests can run reliably.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Company, CompanyMembership, RoleAssignment, User
from app.domain.models.enums import AssignableRole, CompanyStatus, ScopeType
from app.services.auth import hash_password, verify_password


DEFAULT_COMPANY_ID = UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_COMPANY_NAME = "Default Company"

# KazEnergo company (main demo company with full ESG report)
KAZENERGO_COMPANY_ID = UUID("44444444-4444-4444-4444-444444444444")
KAZENERGO_COMPANY_NAME = "KazEnergo JSC"


async def seed_e2e_user(
    session: AsyncSession,
    *,
    email: str = "e2e-test@example.com",
    password: str = "TestPassword123!",
    full_name: str = "E2E Test User",
) -> bool:
    """
    Ensure the E2E user exists and is usable for automated tests.

    Creates/updates:
    - User (is_superuser=True, role=admin)
    - Default company (if missing)
    - Company membership in default company (active)
    - corporate_lead role assignment for default company

    Returns True if any changes were applied.
    """
    changed = False

    # 1) Ensure default company exists (fixed UUID used by multi-tenant migration).
    company = await session.get(Company, DEFAULT_COMPANY_ID)
    if not company:
        # Use raw SQL insert to avoid ORM enum type drift in legacy schemas.
        await session.execute(
            text(
                """
                INSERT INTO companies (
                    company_id, name, slug, status, created_by, created_at_utc, updated_at_utc
                ) VALUES (
                    :company_id, :name, :slug, :status, NULL, now(), now()
                )
                ON CONFLICT (company_id) DO NOTHING
                """
            ),
            {
                "company_id": DEFAULT_COMPANY_ID,
                "name": DEFAULT_COMPANY_NAME,
                "slug": "default-company",
                "status": CompanyStatus.ACTIVE.value,
            },
        )
        await session.flush()
        changed = True

    # 2) Ensure user exists
    user = (
        await session.execute(
            select(User).where(User.email == email)
        )
    ).scalar_one_or_none()

    if not user:
        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            is_active=True,
            is_superuser=True,
        )
        session.add(user)
        await session.flush()
        changed = True
    else:
        # Keep the doc/test credentials stable in dev: update password if mismatch.
        try:
            ok = verify_password(password, user.password_hash)
        except Exception:
            ok = False
        if not ok:
            user.password_hash = hash_password(password)
            changed = True

        if user.full_name != full_name:
            user.full_name = full_name
            changed = True

        if not user.is_superuser:
            user.is_superuser = True
            changed = True

        if not user.is_active:
            user.is_active = True
            changed = True

    # 3) Ensure membership exists
    membership = (
        await session.execute(
            select(CompanyMembership).where(
                CompanyMembership.company_id == DEFAULT_COMPANY_ID,
                CompanyMembership.user_id == user.user_id,
            )
        )
    ).scalar_one_or_none()
    if not membership:
        session.add(
            CompanyMembership(
                company_id=DEFAULT_COMPANY_ID,
                user_id=user.user_id,
                is_active=True,
                created_by=user.user_id,
            )
        )
        changed = True
    else:
        if not membership.is_active:
            membership.is_active = True
            changed = True

    # 4) Ensure corporate_lead role assignment exists for the default company
    role_assignment = (
        await session.execute(
            select(RoleAssignment).where(
                RoleAssignment.company_id == DEFAULT_COMPANY_ID,
                RoleAssignment.user_id == user.user_id,
                RoleAssignment.role == AssignableRole.CORPORATE_LEAD,
                RoleAssignment.scope_type == ScopeType.COMPANY,
                RoleAssignment.scope_id == DEFAULT_COMPANY_ID,
            )
        )
    ).scalar_one_or_none()
    if not role_assignment:
        session.add(
            RoleAssignment(
                company_id=DEFAULT_COMPANY_ID,
                user_id=user.user_id,
                role=AssignableRole.CORPORATE_LEAD,
                scope_type=ScopeType.COMPANY,
                scope_id=DEFAULT_COMPANY_ID,
                created_by=user.user_id,
            )
        )
        changed = True

    return changed


async def seed_corporate_lead_user(
    session: AsyncSession,
    *,
    email: str = "lead@kazenergo.kz",
    password: str = "KazEnergy2024!",
    full_name: str = "Corporate Lead KazEnergo",
) -> bool:
    """
    Ensure the Corporate Lead demo user exists for KazEnergo company.

    Creates/updates:
    - User (is_superuser=False)
    - Company membership in KazEnergo company (active)
    - corporate_lead role assignment

    Returns True if any changes were applied.
    """
    changed = False

    # 1) Ensure KazEnergo company exists
    company = await session.get(Company, KAZENERGO_COMPANY_ID)
    if not company:
        # Use raw SQL insert to avoid ORM enum type drift in legacy schemas.
        await session.execute(
            text(
                """
                INSERT INTO companies (
                    company_id, name, slug, status, created_by, created_at_utc, updated_at_utc
                ) VALUES (
                    :company_id, :name, :slug, :status, NULL, now(), now()
                )
                ON CONFLICT (company_id) DO NOTHING
                """
            ),
            {
                "company_id": KAZENERGO_COMPANY_ID,
                "name": KAZENERGO_COMPANY_NAME,
                "slug": "kazenergo-jsc",
                "status": CompanyStatus.ACTIVE.value,
            },
        )
        await session.flush()
        changed = True

    # 2) Ensure user exists
    user = (
        await session.execute(
            select(User).where(User.email == email)
        )
    ).scalar_one_or_none()

    if not user:
        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            is_active=True,
            is_superuser=False,  # Corporate Lead is NOT superuser
        )
        session.add(user)
        await session.flush()
        changed = True
    else:
        # Update password if mismatch
        try:
            ok = verify_password(password, user.password_hash)
        except Exception:
            ok = False
        if not ok:
            user.password_hash = hash_password(password)
            changed = True

        if user.full_name != full_name:
            user.full_name = full_name
            changed = True

        if not user.is_active:
            user.is_active = True
            changed = True

    # 3) Ensure membership exists
    membership = (
        await session.execute(
            select(CompanyMembership).where(
                CompanyMembership.company_id == KAZENERGO_COMPANY_ID,
                CompanyMembership.user_id == user.user_id,
            )
        )
    ).scalar_one_or_none()
    if not membership:
        session.add(
            CompanyMembership(
                company_id=KAZENERGO_COMPANY_ID,
                user_id=user.user_id,
                is_active=True,
                created_by=user.user_id,
            )
        )
        changed = True
    else:
        if not membership.is_active:
            membership.is_active = True
            changed = True

    # 4) Ensure corporate_lead role assignment exists
    role_assignment = (
        await session.execute(
            select(RoleAssignment).where(
                RoleAssignment.company_id == KAZENERGO_COMPANY_ID,
                RoleAssignment.user_id == user.user_id,
                RoleAssignment.role == AssignableRole.CORPORATE_LEAD,
                RoleAssignment.scope_type == ScopeType.COMPANY,
                RoleAssignment.scope_id == KAZENERGO_COMPANY_ID,
            )
        )
    ).scalar_one_or_none()
    if not role_assignment:
        session.add(
            RoleAssignment(
                company_id=KAZENERGO_COMPANY_ID,
                user_id=user.user_id,
                role=AssignableRole.CORPORATE_LEAD,
                scope_type=ScopeType.COMPANY,
                scope_id=KAZENERGO_COMPANY_ID,
                created_by=user.user_id,
            )
        )
        changed = True

    return changed
