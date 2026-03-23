from app.core.dependencies import RequestContext
from app.core.exceptions import AppError


class EvidencePolicy:
    def can_create(self, ctx: RequestContext) -> None:
        if ctx.role not in ("admin", "esg_manager", "collector", "platform_admin"):
            raise AppError("FORBIDDEN", 403, "You don't have permission to create evidence")

    def can_delete(self, ctx: RequestContext, evidence_created_by: int | None) -> None:
        if ctx.role == "collector" and evidence_created_by != ctx.user_id:
            raise AppError("FORBIDDEN", 403, "Collectors can only delete their own evidence")
        if ctx.role not in ("admin", "esg_manager", "collector", "platform_admin"):
            raise AppError("FORBIDDEN", 403, "You don't have permission to delete evidence")

    async def not_in_approved_scope(self, evidence_repo, evidence_id: int) -> None:
        from app.db.models.evidence import DataPointEvidence
        from app.db.models.data_point import DataPoint
        from sqlalchemy import select, func

        q = (
            select(func.count())
            .select_from(DataPointEvidence)
            .join(DataPoint, DataPoint.id == DataPointEvidence.data_point_id)
            .where(
                DataPointEvidence.evidence_id == evidence_id,
                DataPoint.status == "approved",
            )
        )
        result = await evidence_repo.session.execute(q)
        if result.scalar_one() > 0:
            raise AppError("EVIDENCE_IN_USE", 409, "Cannot delete evidence used in approved data points")
