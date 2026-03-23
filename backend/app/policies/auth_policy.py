from app.core.dependencies import RequestContext
from app.core.exceptions import AppError


class AuthPolicy:
    """Central auth policy — tenant isolation + role checks."""

    @staticmethod
    def check_tenant_isolation(ctx: RequestContext, resource_org_id: int | None) -> None:
        """Ensure user can only access resources in their organization."""
        if ctx.is_platform_admin:
            return  # platform admin can access any tenant
        if resource_org_id is not None and ctx.organization_id != resource_org_id:
            raise AppError("FORBIDDEN", 403, "Access denied — wrong organization")

    @staticmethod
    def require_role(ctx: RequestContext, allowed_roles: list[str]) -> None:
        if ctx.role not in allowed_roles:
            raise AppError(
                "FORBIDDEN", 403,
                f"Role '{ctx.role}' is not allowed. Required: {', '.join(allowed_roles)}"
            )

    @staticmethod
    def require_platform_admin(ctx: RequestContext) -> None:
        if not ctx.is_platform_admin:
            raise AppError("PLATFORM_ADMIN_REQUIRED", 403, "Platform admin access required")

    @staticmethod
    def require_manager_or_admin(ctx: RequestContext) -> None:
        if ctx.role not in ("admin", "esg_manager", "platform_admin"):
            raise AppError("FORBIDDEN", 403, "Only admin or ESG manager can perform this action")

    @staticmethod
    def collector_owns_data_point(ctx: RequestContext, dp_created_by: int | None) -> None:
        """Collector can only edit own data points."""
        if ctx.role == "collector" and dp_created_by != ctx.user_id:
            raise AppError("FORBIDDEN", 403, "You can only edit your own data points")

    @staticmethod
    def reviewer_is_assigned(ctx: RequestContext, reviewer_id: int | None) -> None:
        """Reviewer can only act on assigned reviews."""
        if ctx.role == "reviewer" and reviewer_id != ctx.user_id:
            raise AppError("FORBIDDEN", 403, "You can only review data assigned to you")

    @staticmethod
    def auditor_read_only(ctx: RequestContext) -> None:
        """Auditor cannot perform write operations."""
        if ctx.role == "auditor":
            raise AppError("FORBIDDEN", 403, "Auditor has read-only access")

    @staticmethod
    def require_write_access(ctx: RequestContext) -> None:
        """Block auditor and ensure org context is present."""
        if ctx.role == "auditor":
            raise AppError("FORBIDDEN", 403, "Auditor has read-only access")
        if not ctx.organization_id and not ctx.is_platform_admin:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required for write operations")

    @staticmethod
    def require_reviewer(ctx: RequestContext) -> None:
        """Only reviewer (or admin/manager/platform_admin) can approve/reject."""
        if ctx.role not in ("reviewer", "admin", "esg_manager", "platform_admin"):
            raise AppError(
                "FORBIDDEN", 403,
                "Only reviewers can perform approve/reject actions"
            )

    @staticmethod
    def require_collector_or_manager(ctx: RequestContext) -> None:
        """Only collector, esg_manager, admin, or platform_admin can enter data."""
        if ctx.role not in ("collector", "esg_manager", "admin", "platform_admin"):
            raise AppError(
                "FORBIDDEN", 403,
                "Only collectors or managers can enter data"
            )
