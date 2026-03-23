from app.core.dependencies import RequestContext
from app.core.exceptions import AppError


class ProjectPolicy:
    @staticmethod
    def can_manage(ctx: RequestContext) -> None:
        if ctx.role not in ("admin", "esg_manager", "platform_admin"):
            raise AppError("FORBIDDEN", 403, "Only admin/esg_manager can manage projects")

    @staticmethod
    def can_publish(ctx: RequestContext) -> None:
        if ctx.role not in ("esg_manager", "admin", "platform_admin"):
            raise AppError("FORBIDDEN", 403, "Only esg_manager/admin can publish projects")

    @staticmethod
    def project_not_locked(project_status: str) -> None:
        if project_status == "published":
            raise AppError("PROJECT_LOCKED", 422, "Project is published — editing is blocked")
