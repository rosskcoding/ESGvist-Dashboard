from app.core.dependencies import RequestContext
from app.core.exceptions import AppError


class StandardPolicy:
    def require_admin(self, ctx: RequestContext) -> None:
        if ctx.role not in ("admin", "platform_admin"):
            raise AppError("FORBIDDEN", 403, "Only admin can manage standards")

    def can_deactivate(self, has_disclosures: bool) -> None:
        # Deactivation is always allowed, but deletion is blocked if disclosures exist
        pass

    def can_delete(self, has_disclosures: bool) -> None:
        if has_disclosures:
            raise AppError(
                "STANDARD_IN_USE", 409, "Cannot delete standard with linked disclosures"
            )
