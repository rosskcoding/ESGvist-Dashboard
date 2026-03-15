"""
Common API dependencies.

RBAC system based on AssignableRole and role_assignments table.
Multi-Tenant Security:
- require_tenant_access provides secure-by-default tenant isolation
- All resource access must verify company membership + scoped roles
"""

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user_required
from app.config import settings
from app.domain.models import User
from app.domain.models.enums import AssignableRole, ScopeType
from app.infra.database import get_session

# Type alias for authenticated user dependency
CurrentUser = Annotated[User, Depends(get_current_user_required)]


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

    Raises HTTPException 403 if user doesn't have access.
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


# All tenant-scoped roles used in the system.
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
    RBAC permission checker using AssignableRole system.
    Superuser (is_superuser=true) bypasses all permission checks.
    """

    PERMISSIONS: dict[str, set[AssignableRole]] = {
        # COMPANY MANAGEMENT
        "company:read": {AssignableRole.CORPORATE_LEAD},
        "company:members:invite": {AssignableRole.CORPORATE_LEAD},
        "company:members:update_role": {AssignableRole.CORPORATE_LEAD},
        "company:members:deactivate": {AssignableRole.CORPORATE_LEAD},
        "assignments:manage": {AssignableRole.CORPORATE_LEAD},

        # EVIDENCE
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

        # ESG DASHBOARD
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

        # AUDIT
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

        # PLATFORM (superuser only)
        "platform:company:create": set(),
        "platform:company:read_all": set(),
        "platform:company:update": set(),
        "platform:company:disable": set(),
        "platform:user:create": set(),
        "platform:user:read_all": set(),
        "platform:user:update": set(),
        "platform:user:delete": set(),
        "user:create": set(),
        "user:update": set(),
        "user:delete": set(),
    }

    @classmethod
    def get_user_roles(cls, user: User) -> set[AssignableRole]:
        roles: set[AssignableRole] = set()
        if hasattr(user, "role_assignments") and user.role_assignments:
            for assignment in user.role_assignments:
                try:
                    roles.add(AssignableRole(assignment.role))
                except ValueError:
                    pass
        return roles

    @classmethod
    def get_user_roles_for_company(cls, user: User, company_id: UUID) -> set[AssignableRole]:
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
        if user.is_superuser:
            return True
        allowed_roles = cls.PERMISSIONS.get(permission, set())
        if not allowed_roles:
            return False
        user_roles = cls.get_user_roles(user)
        return bool(user_roles & allowed_roles)

    @classmethod
    def has_company_permission(cls, user: User, permission: str, company_id: UUID) -> bool:
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
        if user.is_superuser:
            return True

        allowed_roles = cls.PERMISSIONS.get(permission, set())
        if not allowed_roles:
            return False

        if not hasattr(user, "role_assignments") or not user.role_assignments:
            return False

        for assignment in user.role_assignments:
            if company_id is not None and assignment.company_id != company_id:
                continue
            try:
                role = AssignableRole(assignment.role)
            except ValueError:
                continue
            if role not in allowed_roles:
                continue

            if assignment.scope_type == ScopeType.COMPANY:
                if company_id and assignment.scope_id == company_id:
                    return True
            elif assignment.scope_type == ScopeType.REPORT:
                if report_id and assignment.scope_id == report_id:
                    return True
            elif assignment.scope_type == ScopeType.SECTION:
                if section_id and assignment.scope_id == section_id:
                    return True

        return False

    @classmethod
    def require_permission(cls, permission: str):
        async def check_permission(
            user: CurrentUser,
            session: Annotated[AsyncSession, Depends(get_session)],
        ) -> None:
            try:
                from sqlalchemy import inspect as sa_inspect
                state = sa_inspect(user)
                if "is_superuser" in getattr(state, "expired_attributes", set()):
                    await session.refresh(user, attribute_names=["is_superuser"])
            except Exception:
                pass

            if not cls.has_permission(user, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {permission}",
                )

        return check_permission

    @classmethod
    def require_superuser(cls):
        async def check_superuser(user: CurrentUser) -> None:
            if not user.is_superuser:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Superuser access required",
                )
        return check_superuser


# Convenience functions
def require_superuser():
    return RBACChecker.require_superuser()


def require_permission(permission: str):
    return RBACChecker.require_permission(permission)
