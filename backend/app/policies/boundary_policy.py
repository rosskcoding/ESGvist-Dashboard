from app.core.dependencies import RequestContext
from app.core.exceptions import AppError


class BoundaryPolicy:
    @staticmethod
    def can_create(ctx: RequestContext) -> None:
        if ctx.role not in ("admin", "platform_admin"):
            raise AppError("FORBIDDEN", 403, "Only admin can create boundaries")

    @staticmethod
    def can_modify_membership(ctx: RequestContext) -> None:
        if ctx.role not in ("admin", "esg_manager", "platform_admin"):
            raise AppError("FORBIDDEN", 403, "Only admin/esg_manager can modify boundary membership")

    @staticmethod
    def snapshot_immutable(project_status: str) -> None:
        if project_status == "published":
            raise AppError("SNAPSHOT_IMMUTABLE", 409, "Cannot modify snapshot of published project")
