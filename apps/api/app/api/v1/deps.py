"""
Common API dependencies.

New RBAC system based on AssignableRole and role_assignments table.
Permissions follow ROLE_PERMISSIONS_MATRIX.md specification.

Multi-Tenant Security:
- ResourceAuthorizer provides secure-by-default tenant isolation
- All resource access must go through ResourceAuthorizer.for_*() methods
- Company boundary is enforced automatically via membership + scoped roles
"""

from dataclasses import dataclass
from typing import Annotated, Callable
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user_required
from app.config import settings
from app.domain.models import Block, Report, Section, User
from app.domain.models.enums import AssignableRole, ScopeType
from app.infra.database import get_session

# Type alias for authenticated user dependency
CurrentUser = Annotated[User, Depends(get_current_user_required)]


# =============================================================================
# Auth Context — returned by ResourceAuthorizer after successful authorization
# =============================================================================


@dataclass
class ReportAuthContext:
    """Authorization context for report-scoped operations."""
    user: User
    company_id: UUID
    report: Report


@dataclass
class SectionAuthContext:
    """Authorization context for section-scoped operations."""
    user: User
    company_id: UUID
    report: Report
    section: Section


@dataclass
class BlockAuthContext:
    """Authorization context for block-scoped operations."""
    user: User
    company_id: UUID
    report: Report
    section: Section
    block: Block


# =============================================================================
# Tenant Isolation Helpers
# =============================================================================


def _has_active_membership(user: User, company_id: UUID) -> bool:
    """Check if user has active membership in company."""
    if not hasattr(user, "memberships") or not user.memberships:
        return False
    return any((m.company_id == company_id and m.is_active) for m in user.memberships)


def _has_any_role_in_company(user: User, company_id: UUID) -> bool:
    """Check if user has any role assignment in company."""
    if not hasattr(user, "role_assignments") or not user.role_assignments:
        return False
    return any((a.company_id == company_id) for a in user.role_assignments)


def require_tenant_access(
    user: User,
    *,
    company_id: UUID,
    permission: str,
    report_id: UUID | None = None,
    section_id: UUID | None = None,
) -> None:
    """
    Enforce tenant isolation + per-company RBAC with scope inheritance.

    Raises HTTPException 403 if:
    - User is not superuser AND
    - User doesn't have active membership in company OR
    - User has no role assignments in company OR
    - User doesn't have required scoped permission

    This is the core security function for multi-tenant isolation.
    """
    if user.is_superuser:
        return

    if not _has_active_membership(user, company_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this company",
        )

    if not _has_any_role_in_company(user, company_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {permission}",
        )

    if not RBACChecker.has_scoped_permission(
        user,
        permission,
        company_id=company_id,
        report_id=report_id,
        section_id=section_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {permission}",
        )


# =============================================================================
# ResourceAuthorizer — Secure-by-Default Resource Authorization
# =============================================================================


class ResourceAuthorizer:
    """
    Secure-by-default resource authorization for multi-tenant SaaS.

    This class provides dependency factories that:
    1. Load the requested resource
    2. Resolve company_id from resource hierarchy (block → section → report → company)
    3. Verify user has active membership in that company
    4. Verify user has required scoped permission
    5. Return authorized context with loaded resources

    Usage:
        @router.post("/releases")
        async def create_release(
            data: ReleaseBuildCreate,
            auth: ReportAuthContext = Depends(ResourceAuthorizer.for_report_body("release:create_draft")),
        ):
            # auth.user, auth.company_id, auth.report are already verified
            ...

    Security Model:
        - Superuser bypasses all checks
        - Regular users must have:
          a) Active membership in the resource's company
          b) Role assignment in that company
          c) Scoped permission covering the resource
    """

    @classmethod
    def for_report(cls, permission: str):
        """
        Authorize access to a report by report_id path parameter.

        Usage:
            @router.get("/reports/{report_id}/something")
            async def handler(
                report_id: UUID,
                auth: ReportAuthContext = Depends(ResourceAuthorizer.for_report("report:read")),
            ):
                # Use auth.report, auth.company_id
        """
        async def authorize(
            report_id: UUID,
            user: CurrentUser,
            session: Annotated[AsyncSession, Depends(get_session)],
        ) -> ReportAuthContext:
            report = await session.get(Report, report_id)
            if not report:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Report {report_id} not found",
                )

            require_tenant_access(
                user,
                company_id=report.company_id,
                permission=permission,
                report_id=report.report_id,
            )

            return ReportAuthContext(
                user=user,
                company_id=report.company_id,
                report=report,
            )

        return authorize

    @classmethod
    def for_report_from_body(cls, permission: str, report_id_field: str = "report_id"):
        """
        Authorize access to a report by report_id from request body.

        This is useful when report_id comes in POST/PUT body instead of path.
        The dependency extracts report_id from the body dynamically.

        Usage:
            @router.post("/releases")
            async def create_release(
                data: ReleaseBuildCreate,  # has report_id field
                auth: ReportAuthContext = Depends(ResourceAuthorizer.for_report_from_body("release:create_draft")),
            ):
                ...
        """
        from fastapi import Request
        import json

        async def authorize(
            request: Request,
            user: CurrentUser,
            session: Annotated[AsyncSession, Depends(get_session)],
        ) -> ReportAuthContext:
            # Parse body to get report_id
            try:
                body = await request.json()
                report_id_str = body.get(report_id_field)
                if not report_id_str:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Missing {report_id_field} in request body",
                    )
                report_id = UUID(report_id_str)
            except (json.JSONDecodeError, ValueError) as e:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid {report_id_field}: {e}",
                )

            report = await session.get(Report, report_id)
            if not report:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Report {report_id} not found",
                )

            require_tenant_access(
                user,
                company_id=report.company_id,
                permission=permission,
                report_id=report.report_id,
            )

            return ReportAuthContext(
                user=user,
                company_id=report.company_id,
                report=report,
            )

        return authorize

    @classmethod
    def for_report_query(cls, permission: str, param_name: str = "report_id"):
        """
        Authorize access to a report by report_id query parameter.

        Usage:
            @router.get("/releases")
            async def list_releases(
                report_id: UUID = Query(...),
                auth: ReportAuthContext = Depends(ResourceAuthorizer.for_report_query("release:read")),
            ):
                ...
        """
        from fastapi import Query

        async def authorize(
            user: CurrentUser,
            session: Annotated[AsyncSession, Depends(get_session)],
            report_id: UUID = Query(..., alias=param_name),
        ) -> ReportAuthContext:
            report = await session.get(Report, report_id)
            if not report:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Report {report_id} not found",
                )

            require_tenant_access(
                user,
                company_id=report.company_id,
                permission=permission,
                report_id=report.report_id,
            )

            return ReportAuthContext(
                user=user,
                company_id=report.company_id,
                report=report,
            )

        return authorize

    @classmethod
    def for_section(cls, permission: str):
        """
        Authorize access to a section by section_id path parameter.

        Resolves: section → report → company

        Usage:
            @router.get("/sections/{section_id}/preview")
            async def preview_section(
                section_id: UUID,
                auth: SectionAuthContext = Depends(ResourceAuthorizer.for_section("preview:read")),
            ):
                ...
        """
        from sqlalchemy.orm import selectinload

        async def authorize(
            section_id: UUID,
            user: CurrentUser,
            session: Annotated[AsyncSession, Depends(get_session)],
        ) -> SectionAuthContext:
            section = await session.get(Section, section_id)
            if not section:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Section {section_id} not found",
                )

            report = await session.get(Report, section.report_id)
            if not report:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Report not found",
                )

            require_tenant_access(
                user,
                company_id=report.company_id,
                permission=permission,
                report_id=report.report_id,
                section_id=section.section_id,
            )

            return SectionAuthContext(
                user=user,
                company_id=report.company_id,
                report=report,
                section=section,
            )

        return authorize

    @classmethod
    def for_block(cls, permission: str):
        """
        Authorize access to a block by block_id path parameter.

        Resolves: block → section → report → company

        Usage:
            @router.get("/blocks/{block_id}/preview")
            async def preview_block(
                block_id: UUID,
                auth: BlockAuthContext = Depends(ResourceAuthorizer.for_block("preview:read")),
            ):
                ...
        """
        async def authorize(
            block_id: UUID,
            user: CurrentUser,
            session: Annotated[AsyncSession, Depends(get_session)],
        ) -> BlockAuthContext:
            block = await session.get(Block, block_id)
            if not block:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Block {block_id} not found",
                )

            section = await session.get(Section, block.section_id)
            if not section:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Section not found",
                )

            report = await session.get(Report, section.report_id)
            if not report:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Report not found",
                )

            require_tenant_access(
                user,
                company_id=report.company_id,
                permission=permission,
                report_id=report.report_id,
                section_id=section.section_id,
            )

            return BlockAuthContext(
                user=user,
                company_id=report.company_id,
                report=report,
                section=section,
                block=block,
            )

        return authorize

    @classmethod
    def for_build(cls, permission: str):
        """
        Authorize access to a build by build_id path parameter.

        Resolves: build → report → company

        Usage:
            @router.get("/releases/{build_id}")
            async def get_build(
                build_id: UUID,
                auth: ReportAuthContext = Depends(ResourceAuthorizer.for_build("release:download")),
            ):
                ...
        """
        from app.domain.models import ReleaseBuild

        async def authorize(
            build_id: UUID,
            user: CurrentUser,
            session: Annotated[AsyncSession, Depends(get_session)],
        ) -> ReportAuthContext:
            build = await session.get(ReleaseBuild, build_id)
            if not build:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Build not found",
                )

            report = await session.get(Report, build.report_id)
            if not report:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Report not found",
                )

            require_tenant_access(
                user,
                company_id=report.company_id,
                permission=permission,
                report_id=report.report_id,
            )

            return ReportAuthContext(
                user=user,
                company_id=report.company_id,
                report=report,
            )

        return authorize

    @classmethod
    def for_translation_job(cls, permission: str):
        """
        Authorize access to a translation job by job_id path parameter.

        Resolves: job → report → company
        """
        from app.domain.models import TranslationJob

        async def authorize(
            job_id: UUID,
            user: CurrentUser,
            session: Annotated[AsyncSession, Depends(get_session)],
        ) -> ReportAuthContext:
            job = await session.get(TranslationJob, job_id)
            if not job:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Job not found",
                )

            report = await session.get(Report, job.report_id)
            if not report:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Report not found",
                )

            require_tenant_access(
                user,
                company_id=report.company_id,
                permission=permission,
                report_id=report.report_id,
            )

            return ReportAuthContext(
                user=user,
                company_id=report.company_id,
                report=report,
            )

        return authorize


# =============================================================================
# Translation Trigger Cost Control
# =============================================================================
#
# TRANSLATION_TRIGGER_RESTRICTED=true (default):
#   - Only Translator + Corporate Lead can trigger LLM auto-translate jobs.
# TRANSLATION_TRIGGER_RESTRICTED=false:
#   - Allow Editor roles to trigger as well (NOT recommended).
#
TRANSLATION_TRIGGER_ROLES: set[AssignableRole] = {
    AssignableRole.TRANSLATOR,
    AssignableRole.CORPORATE_LEAD,
}
if not settings.translation_trigger_restricted:
    TRANSLATION_TRIGGER_ROLES |= {
        AssignableRole.EDITOR,
        AssignableRole.CONTENT_EDITOR,
    }

# All tenant-scoped roles used in the system.
# Checkpoint "save" must be available to every role category.
ALL_TENANT_ROLES: set[AssignableRole] = {
    AssignableRole.CORPORATE_LEAD,
    AssignableRole.EDITOR,
    AssignableRole.CONTENT_EDITOR,
    AssignableRole.SECTION_EDITOR,
    AssignableRole.VIEWER,
    AssignableRole.TRANSLATOR,
    AssignableRole.INTERNAL_AUDITOR,
    AssignableRole.AUDITOR,
    AssignableRole.AUDIT_LEAD,
}


class RBACChecker:
    """
    RBAC permission checker using new AssignableRole system.

    Permissions matrix based on ROLE_PERMISSIONS_MATRIX.md.
    Superuser (is_superuser=true) bypasses all permission checks.
    """

    # Permission -> allowed AssignableRoles
    # Based on ROLE_PERMISSIONS_MATRIX.md specification
    PERMISSIONS: dict[str, set[AssignableRole]] = {
        # ============================================================
        # COMPANY MANAGEMENT
        # ============================================================
        "company:read": {AssignableRole.CORPORATE_LEAD},
        "company:members:invite": {AssignableRole.CORPORATE_LEAD},
        "company:members:update_role": {AssignableRole.CORPORATE_LEAD},
        "company:members:deactivate": {AssignableRole.CORPORATE_LEAD},
        "assignments:manage": {AssignableRole.CORPORATE_LEAD},

        # ============================================================
        # REPORTS
        # ============================================================
        "report:create": {AssignableRole.EDITOR},
        "report:read": {
            AssignableRole.CORPORATE_LEAD,
            AssignableRole.EDITOR,
            AssignableRole.CONTENT_EDITOR,
            AssignableRole.SECTION_EDITOR,
            AssignableRole.VIEWER,
            AssignableRole.TRANSLATOR,
            AssignableRole.INTERNAL_AUDITOR,
            AssignableRole.AUDITOR,
            AssignableRole.AUDIT_LEAD,
        },
        "report:update": {AssignableRole.EDITOR},
        "report:update_meta": {AssignableRole.EDITOR},  # alias for consistency with spec
        "report:delete": {AssignableRole.EDITOR},
        "report:structure:freeze": {AssignableRole.EDITOR},
        "report:structure:unfreeze": {AssignableRole.EDITOR},

        # ============================================================
        # SECTIONS
        # ============================================================
        "section:create": {AssignableRole.EDITOR},
        "section:read": {
            AssignableRole.CORPORATE_LEAD,
            AssignableRole.EDITOR,
            AssignableRole.CONTENT_EDITOR,
            AssignableRole.SECTION_EDITOR,
            AssignableRole.VIEWER,
            AssignableRole.TRANSLATOR,
            AssignableRole.INTERNAL_AUDITOR,
            AssignableRole.AUDITOR,
            AssignableRole.AUDIT_LEAD,
        },
        "section:update": {AssignableRole.EDITOR, AssignableRole.CONTENT_EDITOR},
        "section:update_meta": {AssignableRole.EDITOR, AssignableRole.CONTENT_EDITOR},  # alias
        "section:delete": {AssignableRole.EDITOR},
        "section:reorder": {AssignableRole.EDITOR},
        "section:freeze": {AssignableRole.EDITOR},
        "section:unfreeze": {AssignableRole.EDITOR},

        # ============================================================
        # BLOCKS
        # ============================================================
        "block:create": {AssignableRole.EDITOR, AssignableRole.CONTENT_EDITOR},
        "block:read": {
            AssignableRole.CORPORATE_LEAD,
            AssignableRole.EDITOR,
            AssignableRole.CONTENT_EDITOR,
            AssignableRole.SECTION_EDITOR,
            AssignableRole.VIEWER,
            AssignableRole.TRANSLATOR,
            AssignableRole.INTERNAL_AUDITOR,
            AssignableRole.AUDITOR,
            AssignableRole.AUDIT_LEAD,
        },
        "block:update": {
            AssignableRole.EDITOR,
            AssignableRole.CONTENT_EDITOR,
            AssignableRole.SECTION_EDITOR,
        },
        "block:update_content": {
            AssignableRole.EDITOR,
            AssignableRole.CONTENT_EDITOR,
            AssignableRole.SECTION_EDITOR,
        },
        "block:update_schema": {AssignableRole.EDITOR, AssignableRole.CONTENT_EDITOR},
        "block:delete": {AssignableRole.EDITOR, AssignableRole.CONTENT_EDITOR},
        "block:reorder": {AssignableRole.EDITOR, AssignableRole.CONTENT_EDITOR},
        "block:freeze": {AssignableRole.EDITOR},
        "block:unfreeze": {AssignableRole.EDITOR},

        # ============================================================
        # ASSETS
        # ============================================================
        "asset:read": {
            AssignableRole.CORPORATE_LEAD,
            AssignableRole.EDITOR,
            AssignableRole.CONTENT_EDITOR,
            AssignableRole.SECTION_EDITOR,
            AssignableRole.VIEWER,
            AssignableRole.TRANSLATOR,
            AssignableRole.INTERNAL_AUDITOR,
            AssignableRole.AUDITOR,
            AssignableRole.AUDIT_LEAD,
        },
        "asset:create": {
            AssignableRole.EDITOR,
            AssignableRole.CONTENT_EDITOR,
            AssignableRole.SECTION_EDITOR,
        },
        "asset:delete": {AssignableRole.EDITOR, AssignableRole.CONTENT_EDITOR},

        # ============================================================
        # AUDIT PACK (Export for Auditors)
        # ============================================================
        "audit_pack:generate": {
            AssignableRole.CORPORATE_LEAD,
            AssignableRole.EDITOR,
            AssignableRole.INTERNAL_AUDITOR,
            AssignableRole.AUDITOR,
            AssignableRole.AUDIT_LEAD,
        },
        "audit_pack:download": {
            AssignableRole.CORPORATE_LEAD,
            AssignableRole.EDITOR,
            AssignableRole.INTERNAL_AUDITOR,
            AssignableRole.AUDITOR,
            AssignableRole.AUDIT_LEAD,
        },

        # ============================================================
        # I18N (Internationalization)
        # ============================================================
        "i18n:read": {
            AssignableRole.CORPORATE_LEAD,
            AssignableRole.EDITOR,
            AssignableRole.CONTENT_EDITOR,
            AssignableRole.SECTION_EDITOR,
            AssignableRole.VIEWER,
            AssignableRole.TRANSLATOR,
            AssignableRole.INTERNAL_AUDITOR,
            AssignableRole.AUDITOR,
            AssignableRole.AUDIT_LEAD,
        },
        "i18n:update": {
            AssignableRole.EDITOR,
            AssignableRole.CONTENT_EDITOR,
            AssignableRole.SECTION_EDITOR,
            AssignableRole.TRANSLATOR,
        },
        "block_i18n:update": {
            AssignableRole.EDITOR,
            AssignableRole.CONTENT_EDITOR,
            AssignableRole.SECTION_EDITOR,
            AssignableRole.TRANSLATOR,
        },

        # ============================================================
        # STATUS TRANSITIONS
        # ============================================================
        "status:set_draft": {AssignableRole.EDITOR, AssignableRole.CONTENT_EDITOR},
        "status:set_ready": {AssignableRole.EDITOR, AssignableRole.CONTENT_EDITOR},
        "status:set_qa_required": {AssignableRole.EDITOR},
        "status:approve": {AssignableRole.EDITOR},
        "status:revoke_approval": {AssignableRole.EDITOR},
        "status:to_ready": {AssignableRole.EDITOR, AssignableRole.CONTENT_EDITOR},
        "status:to_qa_required": {AssignableRole.EDITOR},
        "status:rollback": {AssignableRole.EDITOR},

        # ============================================================
        # EVIDENCE
        # ============================================================
        "evidence:create": {
            AssignableRole.EDITOR,
            AssignableRole.CONTENT_EDITOR,
            AssignableRole.SECTION_EDITOR,
            AssignableRole.AUDIT_LEAD,
        },
        "evidence:read": {
            AssignableRole.CORPORATE_LEAD,
            AssignableRole.EDITOR,
            AssignableRole.CONTENT_EDITOR,
            AssignableRole.SECTION_EDITOR,
            AssignableRole.VIEWER,
            AssignableRole.INTERNAL_AUDITOR,
            AssignableRole.AUDITOR,
            AssignableRole.AUDIT_LEAD,
        },
        "evidence:update": {
            AssignableRole.EDITOR,
            AssignableRole.CONTENT_EDITOR,
            AssignableRole.SECTION_EDITOR,
            AssignableRole.AUDIT_LEAD,
        },
        "evidence:delete": {AssignableRole.AUDIT_LEAD, AssignableRole.EDITOR},
        "evidence:download": {
            AssignableRole.CORPORATE_LEAD,
            AssignableRole.EDITOR,
            AssignableRole.CONTENT_EDITOR,
            AssignableRole.SECTION_EDITOR,
            AssignableRole.INTERNAL_AUDITOR,
            AssignableRole.AUDITOR,
            AssignableRole.AUDIT_LEAD,
        },

        # ============================================================
        # ESG DASHBOARD (pillar)
        # ============================================================
        "esg:read": ALL_TENANT_ROLES,
        "esg:write": {
            AssignableRole.CORPORATE_LEAD,
            AssignableRole.EDITOR,
            AssignableRole.CONTENT_EDITOR,
            AssignableRole.SECTION_EDITOR,
        },
        "esg:publish": {
            AssignableRole.CORPORATE_LEAD,
            AssignableRole.EDITOR,
        },

        # ============================================================
        # RELEASES
        # ============================================================
        "release:create": {AssignableRole.CORPORATE_LEAD},
        "release:read": {
            AssignableRole.CORPORATE_LEAD,
            AssignableRole.EDITOR,
        },
        "release:build": {AssignableRole.CORPORATE_LEAD},
        "release:download": {
            AssignableRole.CORPORATE_LEAD,
            AssignableRole.EDITOR,
        },
        "release:create_draft": {AssignableRole.EDITOR},
        "release:create_release": {AssignableRole.CORPORATE_LEAD},

        # ============================================================
        # EXPORTS
        # ============================================================
        "export:draft": {AssignableRole.EDITOR},
        "export:preview": {AssignableRole.EDITOR},

        # ============================================================
        # AUDIT
        # ============================================================
        "audit_check:read": {
            AssignableRole.CORPORATE_LEAD,
            AssignableRole.EDITOR,
            AssignableRole.INTERNAL_AUDITOR,
            AssignableRole.AUDITOR,
            AssignableRole.AUDIT_LEAD,
        },
        "audit_check:update": {
            AssignableRole.AUDITOR,
            AssignableRole.AUDIT_LEAD,
        },
        "audit:finalize_section": {
            AssignableRole.CORPORATE_LEAD,
            AssignableRole.AUDIT_LEAD,
        },
        "audit:finalize_report": {
            AssignableRole.CORPORATE_LEAD,
            AssignableRole.AUDIT_LEAD,
        },

        # ============================================================
        # LOCKS
        # ============================================================
        "lock:coord:apply": {AssignableRole.CORPORATE_LEAD},
        "lock:coord:release": {AssignableRole.CORPORATE_LEAD},
        "lock:audit:apply": {AssignableRole.CORPORATE_LEAD, AssignableRole.AUDIT_LEAD},
        "lock:audit:release": {AssignableRole.CORPORATE_LEAD, AssignableRole.AUDIT_LEAD},
        "lock:audit:override_release": {AssignableRole.CORPORATE_LEAD},

        # ============================================================
        # PLATFORM (superuser only - handled separately)
        # ============================================================
        "platform:company:create": set(),  # superuser only
        "platform:company:read_all": set(),  # superuser only
        "platform:company:update": set(),  # superuser only
        "platform:company:disable": set(),  # superuser only
        "platform:user:create": set(),  # superuser only
        "platform:user:read_all": set(),  # superuser only
        "platform:user:update": set(),  # superuser only
        "platform:user:delete": set(),  # superuser only
        "user:create": set(),  # superuser only
        "user:update": set(),  # superuser only
        "user:delete": set(),  # superuser only

        # ============================================================
        # THEMES (read for all, write for editor)
        # ============================================================
        "theme:read": {
            AssignableRole.CORPORATE_LEAD,
            AssignableRole.EDITOR,
            AssignableRole.CONTENT_EDITOR,
            AssignableRole.SECTION_EDITOR,
            AssignableRole.VIEWER,
            AssignableRole.INTERNAL_AUDITOR,
            AssignableRole.AUDITOR,
            AssignableRole.AUDIT_LEAD,
        },
        "theme:create": {AssignableRole.EDITOR},
        "theme:update": {AssignableRole.EDITOR},
        "theme:delete": set(),  # superuser only

        # ============================================================
        # CHECKPOINTS (Versions / Save)
        # ============================================================
        "checkpoint:create": ALL_TENANT_ROLES,
        "checkpoint:read": ALL_TENANT_ROLES,
        "checkpoint:restore": {AssignableRole.EDITOR, AssignableRole.CORPORATE_LEAD},

        # ============================================================
        # PREVIEW
        # ============================================================
        "preview:read": {
            AssignableRole.CORPORATE_LEAD,
            AssignableRole.EDITOR,
            AssignableRole.CONTENT_EDITOR,
            AssignableRole.SECTION_EDITOR,
            AssignableRole.VIEWER,
            AssignableRole.INTERNAL_AUDITOR,
            AssignableRole.AUDITOR,
            AssignableRole.AUDIT_LEAD,
        },

        # ============================================================
        # TEMPLATES
        # ============================================================
        "template:read": {
            AssignableRole.CORPORATE_LEAD,
            AssignableRole.EDITOR,
            AssignableRole.CONTENT_EDITOR,
            AssignableRole.SECTION_EDITOR,
            AssignableRole.VIEWER,
            AssignableRole.INTERNAL_AUDITOR,
            AssignableRole.AUDITOR,
            AssignableRole.AUDIT_LEAD,
        },
        "template:create": {AssignableRole.EDITOR},
        "template:update": {AssignableRole.EDITOR},
        "template:delete": set(),  # superuser only

        # ============================================================
        # TRANSLATION WORKFLOW
        # ============================================================
        # Trigger LLM auto-translate job (expensive operation)
        "translation:trigger": TRANSLATION_TRIGGER_ROLES,
        # Edit target locale translations manually
        "translation:edit": {
            AssignableRole.TRANSLATOR,
            AssignableRole.EDITOR,
        },
        # Lock/freeze translation units (protect from overwrite)
        "translation:lock": {
            AssignableRole.TRANSLATOR,
            AssignableRole.EDITOR,
        },
        # Submit translation for approval (READY_FOR_APPROVAL)
        "translation:submit": {
            AssignableRole.TRANSLATOR,
            AssignableRole.EDITOR,
        },
        # Approve translations (Editor in Chief)
        "translation:approve": {
            AssignableRole.EDITOR,
        },
        # Force unlock translations (Corporate Lead override)
        "translation:force_unlock": {
            AssignableRole.CORPORATE_LEAD,
        },
        # Retranslate already approved content (Corporate Lead)
        "translation:retranslate_approved": {
            AssignableRole.CORPORATE_LEAD,
        },
        # Read translation jobs/units/progress
        "translation:read": {
            AssignableRole.TRANSLATOR,
            AssignableRole.EDITOR,
            AssignableRole.CONTENT_EDITOR,
            AssignableRole.CORPORATE_LEAD,
            AssignableRole.VIEWER,
        },

        # ============================================================
        # GLOSSARY (for translation)
        # ============================================================
        "glossary:manage": {
            AssignableRole.EDITOR,
            AssignableRole.TRANSLATOR,
        },
    }

    @classmethod
    def get_user_roles(cls, user: User) -> set[AssignableRole]:
        """
        Get all AssignableRoles for a user from their role_assignments.

        Note: This is a simplified version that doesn't check scope.
        For scoped permissions, use has_scoped_permission().
        """
        roles: set[AssignableRole] = set()
        if hasattr(user, "role_assignments") and user.role_assignments:
            for assignment in user.role_assignments:
                try:
                    roles.add(AssignableRole(assignment.role))
                except ValueError:
                    pass  # Skip invalid roles
        return roles

    @classmethod
    def get_user_roles_for_company(cls, user: User, company_id: UUID) -> set[AssignableRole]:
        """
        Get AssignableRoles for a user limited to a specific company.

        This is the safe default for multi-tenant permission checks: roles are per-company.
        """
        roles: set[AssignableRole] = set()
        if not hasattr(user, "role_assignments") or not user.role_assignments:
            return roles
        for assignment in user.role_assignments:
            if assignment.company_id != company_id:
                continue
            try:
                roles.add(AssignableRole(assignment.role))
            except ValueError:
                continue
        return roles

    @classmethod
    def has_permission(cls, user: User, permission: str) -> bool:
        """
        Check if user has a specific permission.

        Superuser bypasses all permission checks.
        """
        # Superuser has all permissions
        if user.is_superuser:
            return True

        allowed_roles = cls.PERMISSIONS.get(permission, set())

        # If no roles can have this permission, only superuser can
        if not allowed_roles:
            return False

        # Check if user has any of the allowed roles
        user_roles = cls.get_user_roles(user)
        return bool(user_roles & allowed_roles)

    @classmethod
    def has_company_permission(cls, user: User, permission: str, company_id: UUID) -> bool:
        """
        Check if user has a permission within a specific company (tenant).

        Superuser bypasses all permission checks.
        """
        if user.is_superuser:
            return True

        allowed_roles = cls.PERMISSIONS.get(permission, set())
        if not allowed_roles:
            return False

        user_roles = cls.get_user_roles_for_company(user, company_id)
        return bool(user_roles & allowed_roles)

    @classmethod
    def has_scoped_permission(
        cls,
        user: User,
        permission: str,
        company_id: UUID | None = None,
        report_id: UUID | None = None,
        section_id: UUID | None = None,
    ) -> bool:
        """
        Check if user has permission within a specific scope.

        Scope hierarchy: company > report > section
        - company scope: applies to all reports/sections in company
        - report scope: applies to all sections in report
        - section scope: applies only to that section

        Superuser bypasses all permission checks.
        """
        if user.is_superuser:
            return True

        allowed_roles = cls.PERMISSIONS.get(permission, set())
        if not allowed_roles:
            return False

        if not hasattr(user, "role_assignments") or not user.role_assignments:
            return False

        for assignment in user.role_assignments:
            # Always enforce tenant boundary: roles are scoped to a company.
            if company_id is not None and assignment.company_id != company_id:
                continue

            try:
                role = AssignableRole(assignment.role)
            except ValueError:
                continue

            if role not in allowed_roles:
                continue

            # Scope hierarchy: company > report > section
            if assignment.scope_type == ScopeType.COMPANY:
                # Company-level role applies to everything in the company
                if company_id and assignment.scope_id == company_id:
                    return True

            elif assignment.scope_type == ScopeType.REPORT:
                # Report-level role applies to report and its sections/blocks
                if report_id and assignment.scope_id == report_id:
                    return True

            elif assignment.scope_type == ScopeType.SECTION:
                # Section-level role applies only to that section (and its blocks)
                if section_id and assignment.scope_id == section_id:
                    return True

        return False

    @classmethod
    def require_permission(cls, permission: str):
        """
        Dependency factory that checks if user has required permission.

        Usage:
            @router.post("/reports")
            async def create_report(
                user: CurrentUser,
                _: None = Depends(RBACChecker.require_permission("report:create")),
            ):
                ...
        """

        async def check_permission(
            user: CurrentUser,
            session: Annotated[AsyncSession, Depends(get_session)],
        ) -> None:
            # In some test/dev flows, the ORM user instance can become expired
            # (e.g. after a rollback). Refresh the superuser flag to avoid
            # triggering async lazy-load outside greenlet context.
            try:
                from sqlalchemy import inspect as sa_inspect

                state = sa_inspect(user)
                if "is_superuser" in getattr(state, "expired_attributes", set()):
                    await session.refresh(user, attribute_names=["is_superuser"])
            except Exception:
                # Fail closed: if we can't safely refresh, the subsequent permission
                # check will deny access unless the attribute is already present.
                pass

            if not cls.has_permission(user, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {permission}",
                )

        return check_permission

    @classmethod
    def require_superuser(cls):
        """Require superuser (platform admin) access."""

        async def check_superuser(user: CurrentUser) -> None:
            if not user.is_superuser:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Superuser access required",
                )

        return check_superuser


# Convenience functions
def require_superuser():
    """Require superuser (platform admin) access."""
    return RBACChecker.require_superuser()


def require_permission(permission: str):
    """Require specific permission."""
    return RBACChecker.require_permission(permission)
