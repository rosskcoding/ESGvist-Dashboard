"""
RBAC Policy Matrix Tests — Data-Driven.

Tests the policy layer (RBACChecker.has_scoped_permission) against the
permission matrix defined in ROLE_PERMISSIONS_MATRIX.md.

Key features:
- Direct policy layer testing (no HTTP, fast)
- Data-driven parametrization (easy to extend)
- Cross-tenant isolation tests
- Scope hierarchy tests (company > report > section)
- Platform Admin (superuser) bypass verification

Run: pytest -q tests/rbac/test_policy_matrix.py
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import RBACChecker
from app.domain.models import (
    Block,
    Company,
    CompanyMembership,
    Report,
    RoleAssignment,
    Section,
    SectionI18n,
    User,
)
from app.domain.models.enums import (
    AssignableRole,
    BlockType,
    BlockVariant,
    CompanyStatus,
    Locale,
    ScopeType,
)


# =============================================================================
# Test Case Data Structure
# =============================================================================


class Expected(str, Enum):
    """Expected outcome of permission check."""
    ALLOW = "ALLOW"
    DENY = "DENY"


@dataclass
class RBACCase:
    """
    Single RBAC test case.

    Attributes:
        case_id: Unique identifier for debugging (e.g., RBAC_001)
        role: The AssignableRole to test (or None for superuser)
        is_superuser: Whether to test as platform admin
        tenant: 'own' for same tenant, 'cross' for cross-tenant test
        scope: Scope level of role assignment
        permission: Permission string to check
        resource_type: Type of resource to check against
        expected: Expected outcome (ALLOW or DENY)
        note: Human-readable explanation
    """
    case_id: str
    role: AssignableRole | None  # None = superuser
    is_superuser: bool
    tenant: Literal["own", "cross"]
    scope: ScopeType
    permission: str
    resource_type: Literal["company", "report", "section", "block"]
    expected: Expected
    note: str


# =============================================================================
# Permission Matrix from ROLE_PERMISSIONS_MATRIX.md
# =============================================================================

# Mapping: permission -> set of roles that have it (from matrix)
PERMISSION_MATRIX: dict[str, set[AssignableRole]] = {
    # COMPANY MANAGEMENT
    "company:read": {AssignableRole.CORPORATE_LEAD},
    "company:members:invite": {AssignableRole.CORPORATE_LEAD},
    "company:members:update_role": {AssignableRole.CORPORATE_LEAD},
    "company:members:deactivate": {AssignableRole.CORPORATE_LEAD},
    "assignments:manage": {AssignableRole.CORPORATE_LEAD},

    # REPORTS
    "report:create": {AssignableRole.EDITOR},
    "report:read": {
        AssignableRole.CORPORATE_LEAD, AssignableRole.EDITOR,
        AssignableRole.CONTENT_EDITOR, AssignableRole.SECTION_EDITOR,
        AssignableRole.VIEWER, AssignableRole.TRANSLATOR,
        AssignableRole.INTERNAL_AUDITOR,
        AssignableRole.AUDITOR, AssignableRole.AUDIT_LEAD,
    },
    "report:update_meta": {AssignableRole.EDITOR},
    "report:delete": {AssignableRole.EDITOR},
    "report:structure:freeze": {AssignableRole.EDITOR},
    "report:structure:unfreeze": {AssignableRole.EDITOR},

    # SECTIONS
    "section:create": {AssignableRole.EDITOR},
    "section:read": {
        AssignableRole.CORPORATE_LEAD, AssignableRole.EDITOR,
        AssignableRole.CONTENT_EDITOR, AssignableRole.SECTION_EDITOR,
        AssignableRole.VIEWER, AssignableRole.TRANSLATOR,
        AssignableRole.INTERNAL_AUDITOR,
        AssignableRole.AUDITOR, AssignableRole.AUDIT_LEAD,
    },
    "section:update_meta": {AssignableRole.EDITOR, AssignableRole.CONTENT_EDITOR},
    "section:delete": {AssignableRole.EDITOR},
    "section:reorder": {AssignableRole.EDITOR},
    "section:freeze": {AssignableRole.EDITOR},
    "section:unfreeze": {AssignableRole.EDITOR},

    # BLOCKS
    "block:create": {AssignableRole.EDITOR, AssignableRole.CONTENT_EDITOR},
    "block:read": {
        AssignableRole.CORPORATE_LEAD, AssignableRole.EDITOR,
        AssignableRole.CONTENT_EDITOR, AssignableRole.SECTION_EDITOR,
        AssignableRole.VIEWER, AssignableRole.TRANSLATOR,
        AssignableRole.INTERNAL_AUDITOR,
        AssignableRole.AUDITOR, AssignableRole.AUDIT_LEAD,
    },
    "block:update_content": {
        AssignableRole.EDITOR, AssignableRole.CONTENT_EDITOR, AssignableRole.SECTION_EDITOR,
    },
    "block:update_schema": {AssignableRole.EDITOR, AssignableRole.CONTENT_EDITOR},
    "block:delete": {AssignableRole.EDITOR, AssignableRole.CONTENT_EDITOR},
    "block:reorder": {AssignableRole.EDITOR, AssignableRole.CONTENT_EDITOR},
    "block:freeze": {AssignableRole.EDITOR},
    "block:unfreeze": {AssignableRole.EDITOR},

    # ASSETS
    "asset:read": {
        AssignableRole.CORPORATE_LEAD, AssignableRole.EDITOR,
        AssignableRole.CONTENT_EDITOR, AssignableRole.SECTION_EDITOR,
        AssignableRole.VIEWER, AssignableRole.TRANSLATOR,
        AssignableRole.INTERNAL_AUDITOR,
        AssignableRole.AUDITOR, AssignableRole.AUDIT_LEAD,
    },
    "asset:create": {AssignableRole.EDITOR, AssignableRole.CONTENT_EDITOR, AssignableRole.SECTION_EDITOR},
    "asset:delete": {AssignableRole.EDITOR, AssignableRole.CONTENT_EDITOR},

    # I18N
    "i18n:read": {
        AssignableRole.CORPORATE_LEAD, AssignableRole.EDITOR,
        AssignableRole.CONTENT_EDITOR, AssignableRole.SECTION_EDITOR,
        AssignableRole.VIEWER, AssignableRole.TRANSLATOR,
        AssignableRole.INTERNAL_AUDITOR,
        AssignableRole.AUDITOR, AssignableRole.AUDIT_LEAD,
    },
    "i18n:update": {
        AssignableRole.EDITOR, AssignableRole.CONTENT_EDITOR,
        AssignableRole.SECTION_EDITOR, AssignableRole.TRANSLATOR,
    },

    # STATUS
    "status:set_draft": {AssignableRole.EDITOR, AssignableRole.CONTENT_EDITOR},
    "status:set_ready": {AssignableRole.EDITOR, AssignableRole.CONTENT_EDITOR},
    "status:set_qa_required": {AssignableRole.EDITOR},
    "status:approve": {AssignableRole.EDITOR},
    "status:revoke_approval": {AssignableRole.EDITOR},

    # EVIDENCE
    "evidence:create": {
        AssignableRole.EDITOR, AssignableRole.CONTENT_EDITOR,
        AssignableRole.SECTION_EDITOR, AssignableRole.AUDIT_LEAD,
    },
    "evidence:read": {
        AssignableRole.CORPORATE_LEAD, AssignableRole.EDITOR,
        AssignableRole.CONTENT_EDITOR, AssignableRole.SECTION_EDITOR,
        AssignableRole.VIEWER, AssignableRole.INTERNAL_AUDITOR,
        AssignableRole.AUDITOR, AssignableRole.AUDIT_LEAD,
    },
    "evidence:update": {
        AssignableRole.EDITOR, AssignableRole.CONTENT_EDITOR,
        AssignableRole.SECTION_EDITOR, AssignableRole.AUDIT_LEAD,
    },
    "evidence:download": {
        AssignableRole.CORPORATE_LEAD, AssignableRole.EDITOR,
        AssignableRole.CONTENT_EDITOR, AssignableRole.SECTION_EDITOR,
        AssignableRole.INTERNAL_AUDITOR, AssignableRole.AUDITOR, AssignableRole.AUDIT_LEAD,
    },

    # RELEASES
    "release:create": {AssignableRole.CORPORATE_LEAD},
    "release:read": {AssignableRole.CORPORATE_LEAD, AssignableRole.EDITOR},
    "release:build": {AssignableRole.CORPORATE_LEAD},
    "release:download": {AssignableRole.CORPORATE_LEAD, AssignableRole.EDITOR},

    # EXPORTS
    "export:draft": {AssignableRole.EDITOR},
    "export:preview": {AssignableRole.EDITOR},

    # AUDIT
    "audit_check:read": {
        AssignableRole.CORPORATE_LEAD, AssignableRole.EDITOR,
        AssignableRole.INTERNAL_AUDITOR, AssignableRole.AUDITOR, AssignableRole.AUDIT_LEAD,
    },
    "audit_check:update": {AssignableRole.AUDITOR, AssignableRole.AUDIT_LEAD},
    "audit:finalize_section": {AssignableRole.CORPORATE_LEAD, AssignableRole.AUDIT_LEAD},
    "audit:finalize_report": {AssignableRole.CORPORATE_LEAD, AssignableRole.AUDIT_LEAD},

    # LOCKS
    "lock:coord:apply": {AssignableRole.CORPORATE_LEAD},
    "lock:coord:release": {AssignableRole.CORPORATE_LEAD},
    "lock:audit:apply": {AssignableRole.CORPORATE_LEAD, AssignableRole.AUDIT_LEAD},
    "lock:audit:release": {AssignableRole.CORPORATE_LEAD, AssignableRole.AUDIT_LEAD},
    "lock:audit:override_release": {AssignableRole.CORPORATE_LEAD},

    # TRANSLATION
    "translation:trigger": {AssignableRole.TRANSLATOR, AssignableRole.CORPORATE_LEAD},
    "translation:edit": {AssignableRole.TRANSLATOR, AssignableRole.EDITOR},
    "translation:lock": {AssignableRole.TRANSLATOR, AssignableRole.EDITOR},
    "translation:submit": {AssignableRole.TRANSLATOR, AssignableRole.EDITOR},
    "translation:approve": {AssignableRole.EDITOR},
    "translation:force_unlock": {AssignableRole.CORPORATE_LEAD},
    "translation:retranslate_approved": {AssignableRole.CORPORATE_LEAD},
    "translation:read": {
        AssignableRole.TRANSLATOR, AssignableRole.EDITOR,
        AssignableRole.CONTENT_EDITOR, AssignableRole.CORPORATE_LEAD,
        AssignableRole.VIEWER,
    },
    "glossary:manage": {AssignableRole.EDITOR, AssignableRole.TRANSLATOR},

    # PLATFORM (superuser only)
    "platform:company:create": set(),
    "platform:company:read_all": set(),
    "platform:company:update": set(),
    "platform:company:disable": set(),
    "platform:user:create": set(),
    "platform:user:read_all": set(),
    "platform:user:update": set(),
    "platform:user:delete": set(),
}

# All roles to test
ALL_ROLES = list(AssignableRole)

# Key permissions per role (for targeted testing)
ROLE_KEY_PERMISSIONS: dict[AssignableRole, list[tuple[str, Expected]]] = {
    AssignableRole.CORPORATE_LEAD: [
        ("company:read", Expected.ALLOW),
        ("company:members:invite", Expected.ALLOW),
        ("release:create", Expected.ALLOW),
        ("release:download", Expected.ALLOW),
        ("lock:coord:apply", Expected.ALLOW),
        ("audit:finalize_report", Expected.ALLOW),
        ("report:create", Expected.DENY),  # Key boundary
        ("block:update_content", Expected.DENY),  # Key boundary
    ],
    AssignableRole.EDITOR: [
        ("report:create", Expected.ALLOW),
        ("report:update_meta", Expected.ALLOW),
        ("report:delete", Expected.ALLOW),
        ("section:freeze", Expected.ALLOW),
        ("block:update_schema", Expected.ALLOW),
        ("status:approve", Expected.ALLOW),
        ("release:read", Expected.ALLOW),
        ("export:preview", Expected.ALLOW),
        ("company:members:invite", Expected.DENY),  # Key boundary
    ],
    AssignableRole.CONTENT_EDITOR: [
        ("block:create", Expected.ALLOW),
        ("block:update_content", Expected.ALLOW),
        ("section:update_meta", Expected.ALLOW),
        ("status:set_ready", Expected.ALLOW),
        ("evidence:download", Expected.ALLOW),  # Per matrix
        ("status:approve", Expected.DENY),  # Key boundary
        ("report:create", Expected.DENY),  # Key boundary
        ("report:structure:freeze", Expected.DENY),  # Key boundary
    ],
    AssignableRole.SECTION_EDITOR: [
        ("block:update_content", Expected.ALLOW),
        ("asset:create", Expected.ALLOW),
        ("i18n:update", Expected.ALLOW),
        ("evidence:create", Expected.ALLOW),
        ("evidence:download", Expected.ALLOW),  # Per matrix
        ("block:create", Expected.DENY),  # Key boundary
        ("status:set_ready", Expected.DENY),  # Key boundary
    ],
    AssignableRole.VIEWER: [
        ("report:read", Expected.ALLOW),
        ("block:read", Expected.ALLOW),
        ("evidence:read", Expected.ALLOW),
        ("evidence:download", Expected.DENY),  # Key boundary
        ("block:update_content", Expected.DENY),
    ],
    AssignableRole.INTERNAL_AUDITOR: [
        ("audit_check:read", Expected.ALLOW),
        ("evidence:download", Expected.ALLOW),
        ("audit_check:update", Expected.DENY),  # Key boundary
        ("block:update_content", Expected.DENY),
    ],
    AssignableRole.AUDITOR: [
        ("audit_check:update", Expected.ALLOW),
        ("audit_check:read", Expected.ALLOW),
        ("evidence:download", Expected.ALLOW),
        ("evidence:create", Expected.DENY),  # Key boundary
        ("audit:finalize_report", Expected.DENY),  # Key boundary
    ],
    AssignableRole.AUDIT_LEAD: [
        ("evidence:create", Expected.ALLOW),
        ("evidence:update", Expected.ALLOW),
        ("audit:finalize_section", Expected.ALLOW),
        ("lock:audit:apply", Expected.ALLOW),
        ("lock:coord:apply", Expected.DENY),  # Key boundary
    ],
    AssignableRole.TRANSLATOR: [
        # Translation workflow permissions
        ("translation:trigger", Expected.ALLOW),
        ("translation:edit", Expected.ALLOW),
        ("translation:lock", Expected.ALLOW),
        ("translation:submit", Expected.ALLOW),
        ("translation:read", Expected.ALLOW),
        ("glossary:manage", Expected.ALLOW),
        ("i18n:update", Expected.ALLOW),
        # Content read permissions
        ("report:read", Expected.ALLOW),
        ("block:read", Expected.ALLOW),
        ("asset:read", Expected.ALLOW),
        # Key boundaries (DENY)
        ("translation:approve", Expected.DENY),  # Only Editor in Chief
        ("translation:force_unlock", Expected.DENY),  # Only Corporate Lead
        ("translation:retranslate_approved", Expected.DENY),  # Only Corporate Lead
        ("block:update_content", Expected.DENY),  # No content editing
        ("block:create", Expected.DENY),  # No content creation
        ("status:approve", Expected.DENY),  # No status management
    ],
}


# =============================================================================
# Fixtures: Companies, Users, Resources
# =============================================================================


@pytest_asyncio.fixture
async def company_a(db_session: AsyncSession) -> Company:
    """Company A — test tenant."""
    company = Company(
        company_id=uuid4(),
        name="Company A (Test Tenant)",
        status=CompanyStatus.ACTIVE,
    )
    db_session.add(company)
    await db_session.flush()
    return company


@pytest_asyncio.fixture
async def company_b(db_session: AsyncSession) -> Company:
    """Company B — cross-tenant isolation target."""
    company = Company(
        company_id=uuid4(),
        name="Company B (Cross-Tenant)",
        status=CompanyStatus.ACTIVE,
    )
    db_session.add(company)
    await db_session.flush()
    return company


@pytest_asyncio.fixture
async def report_a(db_session: AsyncSession, company_a: Company) -> Report:
    """Report in Company A."""
    report = Report(
        report_id=uuid4(),
        company_id=company_a.company_id,
        year=2025,
        title="Report A",
        slug="report-a-2025",
        source_locale=Locale.RU,
        default_locale=Locale.RU,
        enabled_locales=["ru"],
        release_locales=["ru"],
        theme_slug="default",
    )
    db_session.add(report)
    await db_session.flush()
    return report


@pytest_asyncio.fixture
async def report_a2(db_session: AsyncSession, company_a: Company) -> Report:
    """Second report in Company A (for scope tests)."""
    report = Report(
        report_id=uuid4(),
        company_id=company_a.company_id,
        year=2025,
        title="Report A2",
        slug="report-a2-2025",
        source_locale=Locale.RU,
        default_locale=Locale.RU,
        enabled_locales=["ru"],
        release_locales=["ru"],
        theme_slug="default",
    )
    db_session.add(report)
    await db_session.flush()
    return report


@pytest_asyncio.fixture
async def report_b(db_session: AsyncSession, company_b: Company) -> Report:
    """Report in Company B (cross-tenant)."""
    report = Report(
        report_id=uuid4(),
        company_id=company_b.company_id,
        year=2025,
        title="Report B",
        slug="report-b-2025",
        source_locale=Locale.RU,
        default_locale=Locale.RU,
        enabled_locales=["ru"],
        release_locales=["ru"],
        theme_slug="default",
    )
    db_session.add(report)
    await db_session.flush()
    return report


@pytest_asyncio.fixture
async def section_a(db_session: AsyncSession, report_a: Report) -> Section:
    """Section in Report A."""
    section = Section(
        section_id=uuid4(),
        report_id=report_a.report_id,
        order_index=0,
        depth=0,
    )
    db_session.add(section)
    await db_session.flush()

    i18n = SectionI18n(
        section_id=section.section_id,
        locale=Locale.RU,
        title="Section A",
        slug="section-a",
    )
    db_session.add(i18n)
    await db_session.flush()
    return section


@pytest_asyncio.fixture
async def section_a2(db_session: AsyncSession, report_a2: Report) -> Section:
    """Section in Report A2 (for scope tests)."""
    section = Section(
        section_id=uuid4(),
        report_id=report_a2.report_id,
        order_index=0,
        depth=0,
    )
    db_session.add(section)
    await db_session.flush()

    i18n = SectionI18n(
        section_id=section.section_id,
        locale=Locale.RU,
        title="Section A2",
        slug="section-a2",
    )
    db_session.add(i18n)
    await db_session.flush()
    return section


@pytest_asyncio.fixture
async def section_b(db_session: AsyncSession, report_b: Report) -> Section:
    """Section in Report B (cross-tenant)."""
    section = Section(
        section_id=uuid4(),
        report_id=report_b.report_id,
        order_index=0,
        depth=0,
    )
    db_session.add(section)
    await db_session.flush()

    i18n = SectionI18n(
        section_id=section.section_id,
        locale=Locale.RU,
        title="Section B",
        slug="section-b",
    )
    db_session.add(i18n)
    await db_session.flush()
    return section


@pytest_asyncio.fixture
async def block_a(db_session: AsyncSession, report_a: Report, section_a: Section) -> Block:
    """Block in Section A."""
    block = Block(
        block_id=uuid4(),
        report_id=report_a.report_id,
        section_id=section_a.section_id,
        type=BlockType.TEXT,
        variant=BlockVariant.DEFAULT,
        order_index=0,
        data_json={},
        qa_flags_global=[],
    )
    db_session.add(block)
    await db_session.flush()
    return block


@pytest_asyncio.fixture
async def block_b(db_session: AsyncSession, report_b: Report, section_b: Section) -> Block:
    """Block in Section B (cross-tenant)."""
    block = Block(
        block_id=uuid4(),
        report_id=report_b.report_id,
        section_id=section_b.section_id,
        type=BlockType.TEXT,
        variant=BlockVariant.DEFAULT,
        order_index=0,
        data_json={},
        qa_flags_global=[],
    )
    db_session.add(block)
    await db_session.flush()
    return block


# =============================================================================
# User Factory
# =============================================================================


async def create_user_with_role(
    db_session: AsyncSession,
    company: Company,
    role: AssignableRole | None,
    is_superuser: bool = False,
    scope_type: ScopeType = ScopeType.COMPANY,
    scope_id: UUID | None = None,
) -> User:
    """
    Create a user with specified role in company.

    Args:
        db_session: Database session
        company: Company to assign membership
        role: AssignableRole (None for superuser without role)
        is_superuser: Whether user is platform admin
        scope_type: Scope type for role assignment
        scope_id: Scope ID (defaults to company_id if COMPANY scope)
    """
    user = User(
        user_id=uuid4(),
        email=f"test-{role.value if role else 'superuser'}-{uuid4().hex[:6]}@test.com",
        password_hash="not-used",
        full_name=f"Test {role.value if role else 'Superuser'}",
        is_active=True,
        is_superuser=is_superuser,
    )
    db_session.add(user)
    await db_session.flush()

    # Add membership
    membership = CompanyMembership(
        company_id=company.company_id,
        user_id=user.user_id,
        is_active=True,
        created_by=user.user_id,
    )
    db_session.add(membership)

    # Add role assignment (unless superuser without role)
    if role is not None:
        effective_scope_id = scope_id if scope_id else company.company_id
        assignment = RoleAssignment(
            user_id=user.user_id,
            company_id=company.company_id,
            role=role,
            scope_type=scope_type,
            scope_id=effective_scope_id,
            created_by=user.user_id,
        )
        db_session.add(assignment)

    await db_session.flush()
    await db_session.refresh(user, ["memberships", "role_assignments"])
    return user


# =============================================================================
# Test Case Generation
# =============================================================================


def generate_role_permission_cases() -> list[RBACCase]:
    """
    Generate test cases from the permission matrix.

    Creates ~90-110 cases covering:
    - All roles x key permissions (ALLOW/DENY)
    - Cross-tenant denial for each role
    """
    cases: list[RBACCase] = []
    case_num = 0

    # 1. Per-role key permission tests
    for role, permissions in ROLE_KEY_PERMISSIONS.items():
        for permission, expected in permissions:
            case_num += 1
            cases.append(RBACCase(
                case_id=f"RBAC_{case_num:03d}",
                role=role,
                is_superuser=False,
                tenant="own",
                scope=ScopeType.COMPANY,
                permission=permission,
                resource_type="report",
                expected=expected,
                note=f"{role.value}: {permission} = {expected.value}",
            ))

    # 2. Cross-tenant denial tests (all roles except superuser)
    cross_tenant_permissions = ["report:read", "block:update_content", "evidence:download"]
    for role in ALL_ROLES:
        for permission in cross_tenant_permissions:
            case_num += 1
            cases.append(RBACCase(
                case_id=f"RBAC_{case_num:03d}",
                role=role,
                is_superuser=False,
                tenant="cross",
                scope=ScopeType.COMPANY,
                permission=permission,
                resource_type="report",
                expected=Expected.DENY,
                note=f"Cross-tenant: {role.value} → {permission} = DENY",
            ))

    # 3. Superuser tests
    superuser_permissions = [
        ("platform:company:create", Expected.ALLOW),
        ("platform:user:read_all", Expected.ALLOW),
        ("company:members:invite", Expected.ALLOW),
        ("report:delete", Expected.ALLOW),
        ("audit:finalize_report", Expected.ALLOW),
    ]
    for permission, expected in superuser_permissions:
        case_num += 1
        cases.append(RBACCase(
            case_id=f"RBAC_{case_num:03d}",
            role=None,
            is_superuser=True,
            tenant="own",
            scope=ScopeType.COMPANY,
            permission=permission,
            resource_type="company",
            expected=expected,
            note=f"Superuser: {permission} = {expected.value}",
        ))

    # 4. Superuser cross-tenant bypass
    case_num += 1
    cases.append(RBACCase(
        case_id=f"RBAC_{case_num:03d}",
        role=None,
        is_superuser=True,
        tenant="cross",
        scope=ScopeType.COMPANY,
        permission="report:delete",
        resource_type="report",
        expected=Expected.ALLOW,
        note="Superuser bypasses cross-tenant",
    ))

    return cases


# Generate all cases at module load
ALL_CASES = generate_role_permission_cases()


def case_id_func(case: RBACCase) -> str:
    """Generate readable test ID."""
    role_name = case.role.value if case.role else "superuser"
    return f"{case.case_id}_{role_name}_{case.permission}_{case.tenant}"


# =============================================================================
# Main Parametrized Test
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ALL_CASES, ids=case_id_func)
async def test_rbac_policy_matrix(
    db_session: AsyncSession,
    company_a: Company,
    company_b: Company,
    report_a: Report,
    report_b: Report,
    section_a: Section,
    section_b: Section,
    case: RBACCase,
):
    """
    Data-driven RBAC policy test.

    Tests RBACChecker.has_scoped_permission() against the permission matrix.
    """
    # Select target company based on tenant
    target_company = company_a if case.tenant == "own" else company_b
    user_company = company_a  # User always belongs to Company A

    # Select target resource IDs
    if case.tenant == "own":
        target_report_id = report_a.report_id
        target_section_id = section_a.section_id
        target_company_id = company_a.company_id
    else:
        target_report_id = report_b.report_id
        target_section_id = section_b.section_id
        target_company_id = company_b.company_id

    # Create user with role
    user = await create_user_with_role(
        db_session,
        company=user_company,
        role=case.role,
        is_superuser=case.is_superuser,
        scope_type=case.scope,
    )

    # Call policy layer
    result = RBACChecker.has_scoped_permission(
        user=user,
        permission=case.permission,
        company_id=target_company_id,
        report_id=target_report_id,
        section_id=target_section_id,
    )

    # Assert
    expected_bool = case.expected == Expected.ALLOW
    assert result == expected_bool, (
        f"\n{'='*60}\n"
        f"RBAC POLICY TEST FAILED: {case.case_id}\n"
        f"{'='*60}\n"
        f"Role:       {case.role.value if case.role else 'superuser'}\n"
        f"Superuser:  {case.is_superuser}\n"
        f"Permission: {case.permission}\n"
        f"Tenant:     {case.tenant}\n"
        f"Scope:      {case.scope.value}\n"
        f"Expected:   {case.expected.value}\n"
        f"Got:        {'ALLOW' if result else 'DENY'}\n"
        f"Note:       {case.note}\n"
        f"{'='*60}"
    )


# =============================================================================
# Scope Hierarchy Tests
# =============================================================================


@pytest.mark.asyncio
async def test_content_editor_report_scope_allows_own_report(
    db_session: AsyncSession,
    company_a: Company,
    report_a: Report,
    section_a: Section,
):
    """Content Editor with report-scope CAN edit blocks in assigned report."""
    user = await create_user_with_role(
        db_session,
        company=company_a,
        role=AssignableRole.CONTENT_EDITOR,
        scope_type=ScopeType.REPORT,
        scope_id=report_a.report_id,
    )

    result = RBACChecker.has_scoped_permission(
        user=user,
        permission="block:update_content",
        company_id=company_a.company_id,
        report_id=report_a.report_id,
        section_id=section_a.section_id,
    )

    assert result is True, "Content Editor should have block:update_content in assigned report"


@pytest.mark.asyncio
async def test_content_editor_report_scope_denies_other_report(
    db_session: AsyncSession,
    company_a: Company,
    report_a: Report,
    report_a2: Report,
    section_a2: Section,
):
    """Content Editor with report-scope CANNOT edit blocks in other report."""
    user = await create_user_with_role(
        db_session,
        company=company_a,
        role=AssignableRole.CONTENT_EDITOR,
        scope_type=ScopeType.REPORT,
        scope_id=report_a.report_id,  # Assigned to report_a
    )

    result = RBACChecker.has_scoped_permission(
        user=user,
        permission="block:update_content",
        company_id=company_a.company_id,
        report_id=report_a2.report_id,  # Checking report_a2
        section_id=section_a2.section_id,
    )

    assert result is False, "Content Editor should NOT have access to other report"


@pytest.mark.asyncio
async def test_section_editor_section_scope_allows_own_section(
    db_session: AsyncSession,
    company_a: Company,
    report_a: Report,
    section_a: Section,
):
    """Section Editor (SME) with section-scope CAN edit blocks in assigned section."""
    user = await create_user_with_role(
        db_session,
        company=company_a,
        role=AssignableRole.SECTION_EDITOR,
        scope_type=ScopeType.SECTION,
        scope_id=section_a.section_id,
    )

    result = RBACChecker.has_scoped_permission(
        user=user,
        permission="block:update_content",
        company_id=company_a.company_id,
        report_id=report_a.report_id,
        section_id=section_a.section_id,
    )

    assert result is True, "Section Editor should have block:update_content in assigned section"


@pytest.mark.asyncio
async def test_section_editor_section_scope_denies_other_section(
    db_session: AsyncSession,
    company_a: Company,
    report_a: Report,
    report_a2: Report,
    section_a: Section,
    section_a2: Section,
):
    """Section Editor (SME) with section-scope CANNOT edit blocks in other section."""
    user = await create_user_with_role(
        db_session,
        company=company_a,
        role=AssignableRole.SECTION_EDITOR,
        scope_type=ScopeType.SECTION,
        scope_id=section_a.section_id,  # Assigned to section_a
    )

    result = RBACChecker.has_scoped_permission(
        user=user,
        permission="block:update_content",
        company_id=company_a.company_id,
        report_id=report_a2.report_id,  # Checking section_a2
        section_id=section_a2.section_id,
    )

    assert result is False, "Section Editor should NOT have access to other section"


# =============================================================================
# Negative Tests (Fail-Closed)
# =============================================================================


@pytest.mark.asyncio
async def test_unknown_permission_denied(
    db_session: AsyncSession,
    company_a: Company,
    report_a: Report,
):
    """Unknown permission should be DENIED (fail-closed)."""
    user = await create_user_with_role(
        db_session,
        company=company_a,
        role=AssignableRole.EDITOR,
    )

    result = RBACChecker.has_scoped_permission(
        user=user,
        permission="unknown:nonexistent:permission",
        company_id=company_a.company_id,
        report_id=report_a.report_id,
    )

    assert result is False, "Unknown permission should be DENIED"


@pytest.mark.asyncio
async def test_no_role_assignment_denied(
    db_session: AsyncSession,
    company_a: Company,
    report_a: Report,
):
    """User with membership but no role assignment should be DENIED."""
    # Create user with membership but no role
    user = User(
        user_id=uuid4(),
        email=f"no-role-{uuid4().hex[:6]}@test.com",
        password_hash="not-used",
        full_name="No Role User",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.flush()

    membership = CompanyMembership(
        company_id=company_a.company_id,
        user_id=user.user_id,
        is_active=True,
        created_by=user.user_id,
    )
    db_session.add(membership)
    await db_session.flush()
    await db_session.refresh(user, ["memberships", "role_assignments"])

    result = RBACChecker.has_scoped_permission(
        user=user,
        permission="report:read",
        company_id=company_a.company_id,
        report_id=report_a.report_id,
    )

    assert result is False, "User without role should be DENIED"


@pytest.mark.asyncio
async def test_no_company_id_denied(
    db_session: AsyncSession,
    company_a: Company,
):
    """Permission check without company_id should be DENIED."""
    user = await create_user_with_role(
        db_session,
        company=company_a,
        role=AssignableRole.EDITOR,
    )

    result = RBACChecker.has_scoped_permission(
        user=user,
        permission="report:read",
        company_id=None,  # No company context
        report_id=None,
    )

    assert result is False, "Check without company_id should be DENIED"


# =============================================================================
# Summary Statistics
# =============================================================================


def test_case_count():
    """Verify we have sufficient test coverage (target: 80-120 cases)."""
    count = len(ALL_CASES)
    print(f"\n✅ Generated {count} RBAC test cases")
    assert 40 <= count <= 150, f"Expected 40-150 cases, got {count}"


def test_all_roles_covered():
    """Verify all roles have test cases."""
    tested_roles = {case.role for case in ALL_CASES if case.role is not None}
    missing = set(ALL_ROLES) - tested_roles
    assert not missing, f"Missing test cases for roles: {missing}"


