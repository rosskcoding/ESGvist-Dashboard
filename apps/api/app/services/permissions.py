"""
PermissionService — Scoped RBAC permission checker.

Replaces flat RBACChecker with scoped permission checks:
- Tenant isolation via CompanyMembership
- Scoped roles via RoleAssignment
- Platform admin via is_superuser
"""

from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import (
    AssignableRole,
    Block,
    CompanyMembership,
    Report,
    RoleAssignment,
    ScopeType,
    Section,
    User,
)

# =============================================================================
# Permission Definitions
# =============================================================================

# Permissions that each role grants
ROLE_PERMISSIONS: dict[AssignableRole, set[str]] = {
    # =========================================================================
    # CORPORATE LEAD — company lead
    # Company management, releases, audit override
    # =========================================================================
    AssignableRole.CORPORATE_LEAD: {
        # Company management
        "company:read",
        "company:members:invite",
        "company:members:update_role",
        "company:members:deactivate",
        "assignments:manage",
        # Content read-only
        "report:read",
        "section:read",
        "block:read",
        "i18n:read",
        "evidence:read",
        "evidence:download",
        "audit_check:read",
        # ESG dashboard (pillar)
        "esg:read",
        "esg:write",
        "esg:publish",
        # Assets (read-only)
        "asset:read",
        # Releases (full control)
        "release:create",
        "release:read",
        "release:build",
        "release:download",
        # Audit override
        "lock:coord:apply",
        "lock:coord:release",
        "lock:audit:apply",
        "lock:audit:release",
        "lock:audit:override_release",
        "audit:finalize_section",
        "audit:finalize_report",
        # Translation overrides
        "translation:trigger",
        "translation:read",
        "translation:force_unlock",
        "translation:retranslate_approved",
    },

    # =========================================================================
    # EDITOR IN CHIEF — editor-in-chief
    # Full CRUD + freeze + approve + draft exports + releases read
    # =========================================================================
    AssignableRole.EDITOR: {
        # Reports (full CRUD)
        "report:create",
        "report:read",
        "report:update_meta",
        "report:delete",
        # Structure freeze/unfreeze
        "report:structure:freeze",
        "report:structure:unfreeze",
        # Sections (full CRUD + freeze)
        "section:create",
        "section:read",
        "section:update_meta",
        "section:delete",
        "section:reorder",
        "section:freeze",
        "section:unfreeze",
        # Blocks (full CRUD + freeze)
        "block:create",
        "block:read",
        "block:update_content",
        "block:update_schema",
        "block:delete",
        "block:reorder",
        "block:freeze",
        "block:unfreeze",
        # Assets (full CRUD)
        "asset:read",
        "asset:create",
        "asset:delete",
        # I18n
        "i18n:read",
        "i18n:update",
        "block_i18n:update",
        # Status (including approve)
        "status:set_draft",
        "status:set_ready",
        "status:set_qa_required",
        "status:approve",
        "status:revoke_approval",
        # Evidence
        "evidence:create",
        "evidence:read",
        "evidence:update",
        "evidence:download",
        # Releases (read + download)
        "release:read",
        "release:download",
        # Draft exports
        "export:draft",
        "export:preview",
        # Audit check read (for QA)
        "audit_check:read",
        # Translation (edit, lock, submit, approve)
        "translation:edit",
        "translation:lock",
        "translation:submit",
        "translation:approve",
        "translation:read",
        "glossary:manage",
        # ESG dashboard (pillar)
        "esg:read",
        "esg:write",
        "esg:publish",
    },

    # =========================================================================
    # EDITOR (CONTENT_EDITOR) — content editor (scoped)
    # Can edit only within assigned scope
    # =========================================================================
    AssignableRole.CONTENT_EDITOR: {
        # Reports (read only)
        "report:read",
        # Sections (read + update)
        "section:read",
        "section:update_meta",
        # Blocks (CRUD where assigned)
        "block:create",
        "block:read",
        "block:update_content",
        "block:update_schema",
        "block:delete",
        "block:reorder",
        # Assets (full CRUD — needed for block content)
        "asset:read",
        "asset:create",
        "asset:delete",
        # I18n
        "i18n:read",
        "i18n:update",
        # Status (can set ready, but NOT approve)
        "status:set_draft",
        "status:set_ready",
        # Evidence
        "evidence:create",
        "evidence:read",
        "evidence:update",
        "evidence:download",
        # ESG dashboard (pillar)
        "esg:read",
        "esg:write",
    },

    # =========================================================================
    # SECTION EDITOR (SME) — subject-matter expert
    # =========================================================================
    AssignableRole.SECTION_EDITOR: {
        "report:read",
        "section:read",
        "block:read",
        "block:update_content",
        # Assets (read + create for attaching to blocks)
        "asset:read",
        "asset:create",
        "i18n:read",
        "i18n:update",
        "evidence:create",
        "evidence:read",
        "evidence:update",
        "evidence:download",
        # ESG dashboard (pillar)
        "esg:read",
        "esg:write",
    },

    # =========================================================================
    # VIEWER — read-only
    # =========================================================================
    AssignableRole.VIEWER: {
        "report:read",
        "section:read",
        "block:read",
        "asset:read",
        "i18n:read",
        "evidence:read",
        # ESG dashboard (pillar)
        "esg:read",
    },

    # =========================================================================
    # INTERNAL AUDITOR — internal audit (company employees)
    # Read-only: content, evidence, audit checks
    # =========================================================================
    AssignableRole.INTERNAL_AUDITOR: {
        "report:read",
        "section:read",
        "block:read",
        "asset:read",
        "i18n:read",
        "evidence:read",
        "evidence:download",
        "audit_check:read",
        # ESG dashboard (pillar)
        "esg:read",
    },

    # =========================================================================
    # AUDITOR — external auditor (limited access)
    # Read-only: content, evidence, audit checks
    # =========================================================================
    AssignableRole.AUDITOR: {
        "report:read",
        "section:read",
        "block:read",
        "asset:read",
        "i18n:read",
        "evidence:read",
        "evidence:download",
        "audit_check:read",
        "audit_check:update",
        # ESG dashboard (pillar)
        "esg:read",
    },

    # =========================================================================
    # AUDIT LEAD — lead external auditor
    # Same as Auditor but can finalize and manage locks
    # =========================================================================
    AssignableRole.AUDIT_LEAD: {
        "report:read",
        "section:read",
        "block:read",
        "asset:read",
        "i18n:read",
        "evidence:read",
        "evidence:download",
        "audit_check:read",
        "audit_check:update",
        "audit:finalize_section",
        "audit:finalize_report",
        "lock:audit:apply",
        "lock:audit:release",
        # ESG dashboard (pillar)
        "esg:read",
    },

    # =========================================================================
    # TRANSLATOR — translator/localizer
    # Translation workflow: trigger, edit, lock, submit translations
    # =========================================================================
    AssignableRole.TRANSLATOR: {
        # Read permissions for content access
        "report:read",
        "section:read",
        "block:read",
        "asset:read",
        "i18n:read",
        "i18n:update",
        "block_i18n:update",
        # Translation workflow
        "translation:trigger",      # Run auto-translate (LLM)
        "translation:edit",         # Edit target locale translations
        "translation:lock",         # Lock/freeze translation units
        "translation:submit",       # Submit for approval
        "translation:read",         # Read translation jobs/progress
        # Glossary management
        "glossary:manage",
        # ESG dashboard (pillar)
        "esg:read",
    },

}

# Checkpoint "save" (manual version snapshot) is available to all tenant roles.
_CHECKPOINT_COMMON_PERMISSIONS = {"checkpoint:create", "checkpoint:read"}
for _role in ROLE_PERMISSIONS:
    ROLE_PERMISSIONS[_role].update(_CHECKPOINT_COMMON_PERMISSIONS)

# Platform admin permissions
PLATFORM_PERMISSIONS = {
    "platform:company:create",
    "platform:company:read_all",
    "platform:company:update",
    "platform:company:disable",
}


class PermissionService:
    """
    Scoped permission checker.

    Check order:
    1. Platform admin (is_superuser) - has all permissions
    2. Company owner/admin - has company-level permissions
    3. Role assignments - scoped permissions
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def check_platform_admin(self, user: User) -> bool:
        """Check if user is platform admin (superuser)."""
        return user.is_superuser

    async def get_membership(
        self, user_id: UUID, company_id: UUID
    ) -> CompanyMembership | None:
        """Get user's membership in company."""
        result = await self.session.execute(
            select(CompanyMembership).where(
                and_(
                    CompanyMembership.user_id == user_id,
                    CompanyMembership.company_id == company_id,
                    CompanyMembership.is_active == True,  # noqa: E712
                )
            )
        )
        return result.scalar_one_or_none()

    async def check_tenant_access(self, user: User, company_id: UUID) -> bool:
        """
        Check if user has access to company (tenant).

        Returns True if:
        - User is platform admin (superuser)
        - User has active membership in company
        """
        if user.is_superuser:
            return True

        membership = await self.get_membership(user.user_id, company_id)
        return membership is not None

    async def require_tenant_access(self, user: User, company_id: UUID) -> None:
        """Raise if user doesn't have tenant access."""
        if not await self.check_tenant_access(user, company_id):
            raise PermissionError(f"No access to company {company_id}")

    async def get_role_assignments(
        self,
        user_id: UUID,
        company_id: UUID,
        scope_type: ScopeType | None = None,
        scope_id: UUID | None = None,
    ) -> list[RoleAssignment]:
        """Get user's role assignments in company."""
        query = select(RoleAssignment).where(
            and_(
                RoleAssignment.user_id == user_id,
                RoleAssignment.company_id == company_id,
            )
        )

        if scope_type:
            query = query.where(RoleAssignment.scope_type == scope_type)
        if scope_id:
            query = query.where(RoleAssignment.scope_id == scope_id)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def resolve_scope_chain(
        self, scope_type: ScopeType, scope_id: UUID
    ) -> list[tuple[ScopeType, UUID]]:
        """
        Resolve scope hierarchy for permission check.

        Returns list of (scope_type, scope_id) from specific to general:
        - section -> report -> company
        - report -> company
        - company
        """
        chain = [(scope_type, scope_id)]

        if scope_type == ScopeType.SECTION:
            # Get section's report
            result = await self.session.execute(
                select(Section.report_id).where(Section.section_id == scope_id)
            )
            report_id = result.scalar_one_or_none()
            if report_id:
                chain.append((ScopeType.REPORT, report_id))
                # Get report's company
                result = await self.session.execute(
                    select(Report.company_id).where(Report.report_id == report_id)
                )
                company_id = result.scalar_one_or_none()
                if company_id:
                    chain.append((ScopeType.COMPANY, company_id))

        elif scope_type == ScopeType.REPORT:
            # Get report's company
            result = await self.session.execute(
                select(Report.company_id).where(Report.report_id == scope_id)
            )
            company_id = result.scalar_one_or_none()
            if company_id:
                chain.append((ScopeType.COMPANY, company_id))

        return chain

    async def get_company_id_for_scope(
        self, scope_type: ScopeType, scope_id: UUID
    ) -> UUID | None:
        """Get company_id for any scope."""
        if scope_type == ScopeType.COMPANY:
            return scope_id

        chain = await self.resolve_scope_chain(scope_type, scope_id)
        for st, sid in chain:
            if st == ScopeType.COMPANY:
                return sid
        return None

    async def check_permission(
        self,
        user: User,
        permission: str,
        scope_type: ScopeType | None = None,
        scope_id: UUID | None = None,
        locale: str | None = None,
    ) -> bool:
        """
        Check if user has permission in scope.

        Args:
            user: User to check
            permission: Permission string (e.g., "block:update_content")
            scope_type: Scope type (company, report, section)
            scope_id: ID of the scoped entity
            locale: Locale for locale-scoped permission check

        Returns:
            True if user has permission
        """
        # Platform admin has all permissions
        if user.is_superuser:
            return True

        # Platform-only permissions
        if permission.startswith("platform:"):
            return False  # Only superuser can do platform ops

        # Get company_id for scope
        if scope_type and scope_id:
            company_id = await self.get_company_id_for_scope(scope_type, scope_id)
        else:
            return False  # Need scope for non-platform permissions

        if not company_id:
            return False

        # Check membership (user must be member of company)
        membership = await self.get_membership(user.user_id, company_id)
        if not membership:
            return False

        # Check role assignments
        scope_chain = []
        if scope_type and scope_id:
            scope_chain = await self.resolve_scope_chain(scope_type, scope_id)

        # Get all assignments for this user in this company
        assignments = await self.get_role_assignments(user.user_id, company_id)

        for assignment in assignments:
            # Check if assignment scope matches any in the chain
            assignment_scope = (assignment.scope_type, assignment.scope_id)
            if assignment_scope not in scope_chain:
                continue

            # Check if role has the permission
            role_permissions = ROLE_PERMISSIONS.get(assignment.role, set())
            if permission in role_permissions:
                return True

        return False

    async def require_permission(
        self,
        user: User,
        permission: str,
        scope_type: ScopeType | None = None,
        scope_id: UUID | None = None,
        locale: str | None = None,
    ) -> None:
        """Raise if user doesn't have permission."""
        if not await self.check_permission(user, permission, scope_type, scope_id, locale):
            raise PermissionError(f"Permission denied: {permission}")

    async def get_user_permissions(
        self,
        user: User,
        scope_type: ScopeType,
        scope_id: UUID,
    ) -> set[str]:
        """Get all permissions user has in scope."""
        permissions: set[str] = set()

        if user.is_superuser:
            # Superuser has all permissions
            for role_perms in ROLE_PERMISSIONS.values():
                permissions.update(role_perms)
            permissions.update(PLATFORM_PERMISSIONS)
            return permissions

        company_id = await self.get_company_id_for_scope(scope_type, scope_id)
        if not company_id:
            return permissions

        membership = await self.get_membership(user.user_id, company_id)
        if not membership:
            return permissions

        # Add role-based permissions
        scope_chain = await self.resolve_scope_chain(scope_type, scope_id)
        assignments = await self.get_role_assignments(user.user_id, company_id)

        for assignment in assignments:
            if (assignment.scope_type, assignment.scope_id) in scope_chain:
                role_perms = ROLE_PERMISSIONS.get(assignment.role, set())
                permissions.update(role_perms)

        return permissions


# =============================================================================
# Helper Functions
# =============================================================================


async def get_report_company_id(session: AsyncSession, report_id: UUID) -> UUID | None:
    """Get company_id for a report."""
    result = await session.execute(
        select(Report.company_id).where(Report.report_id == report_id)
    )
    return result.scalar_one_or_none()


async def get_section_report_id(session: AsyncSession, section_id: UUID) -> UUID | None:
    """Get report_id for a section."""
    result = await session.execute(
        select(Section.report_id).where(Section.section_id == section_id)
    )
    return result.scalar_one_or_none()


async def get_block_section_id(session: AsyncSession, block_id: UUID) -> UUID | None:
    """Get section_id for a block."""
    result = await session.execute(
        select(Block.section_id).where(Block.block_id == block_id)
    )
    return result.scalar_one_or_none()
