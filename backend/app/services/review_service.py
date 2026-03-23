import logging

from sqlalchemy import select

from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.db.models.project import MetricAssignment
from app.repositories.audit_repo import AuditRepository
from app.repositories.data_point_repo import DataPointRepository
from app.repositories.notification_repo import NotificationRepository
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class ReviewService:
    def __init__(
        self,
        dp_repo: DataPointRepository,
        audit_repo: AuditRepository | None = None,
        notification_repo: NotificationRepository | None = None,
    ):
        self.dp_repo = dp_repo
        self.audit_repo = audit_repo
        self.notification_service = (
            NotificationService(notification_repo) if notification_repo else None
        )

    async def _audit(self, action: str, dp_id: int, ctx: RequestContext, changes: dict | None = None):
        if self.audit_repo:
            await self.audit_repo.log(
                entity_type="DataPoint",
                entity_id=dp_id,
                action=action,
                user_id=ctx.user_id,
                organization_id=ctx.organization_id,
                changes=changes,
            )

    async def _notify_collector(self, dp, action: str, ctx: RequestContext, comment: str | None = None):
        """Notify the collector (created_by) about the review decision."""
        if not self.notification_service or not ctx.organization_id:
            return
        if not dp.created_by:
            return

        title_map = {
            "approved": "Data point approved",
            "rejected": "Data point rejected",
            "needs_revision": "Revision requested",
        }
        message_map = {
            "approved": f"Data point #{dp.id} has been approved.",
            "rejected": f"Data point #{dp.id} has been rejected. Reason: {comment or 'N/A'}",
            "needs_revision": f"Data point #{dp.id} needs revision. Comment: {comment or 'N/A'}",
        }

        try:
            await self.notification_service.notify(
                user_id=dp.created_by,
                org_id=ctx.organization_id,
                type=f"data_point_{action}",
                title=title_map.get(action, f"Data point {action}"),
                message=message_map.get(action, f"Data point #{dp.id} status changed to {action}"),
                entity_type="DataPoint",
                entity_id=dp.id,
                triggered_by=ctx.user_id,
            )
        except Exception as e:
            logger.warning("Failed to send notification for dp %d: %s", dp.id, e)

    async def batch_approve(
        self, dp_ids: list[int], comment: str | None, ctx: RequestContext
    ) -> dict:
        results = []
        for dp_id in dp_ids:
            dp = await self.dp_repo.get_or_raise(dp_id)
            if dp.status != "in_review":
                results.append({"id": dp_id, "success": False, "reason": f"Status is '{dp.status}', expected 'in_review'"})
                continue
            await self.dp_repo.update(dp_id, status="approved", review_comment=comment)
            await self._audit("data_point_approved", dp_id, ctx, {"comment": comment})
            await self._notify_collector(dp, "approved", ctx, comment)
            results.append({"id": dp_id, "success": True, "status": "approved"})
        return {"results": results, "approved_count": sum(1 for r in results if r["success"])}

    async def batch_reject(
        self, dp_ids: list[int], comment: str | None, ctx: RequestContext
    ) -> dict:
        if not comment:
            raise AppError("REVIEW_COMMENT_REQUIRED", 422, "Comment is required for batch reject")

        results = []
        for dp_id in dp_ids:
            dp = await self.dp_repo.get_or_raise(dp_id)
            if dp.status != "in_review":
                results.append({"id": dp_id, "success": False, "reason": f"Status is '{dp.status}'"})
                continue
            await self.dp_repo.update(dp_id, status="rejected", review_comment=comment)
            await self._audit("data_point_rejected", dp_id, ctx, {"comment": comment, "reason_code": "reviewer_rejection"})
            await self._notify_collector(dp, "rejected", ctx, comment)
            results.append({"id": dp_id, "success": True, "status": "rejected"})
        return {"results": results, "rejected_count": sum(1 for r in results if r["success"])}

    async def batch_request_revision(
        self, dp_ids: list[int], comment: str | None, ctx: RequestContext
    ) -> dict:
        if not comment:
            raise AppError("REVIEW_COMMENT_REQUIRED", 422, "Comment is required for request revision")

        results = []
        for dp_id in dp_ids:
            dp = await self.dp_repo.get_or_raise(dp_id)
            if dp.status != "in_review":
                results.append({"id": dp_id, "success": False, "reason": f"Status is '{dp.status}'"})
                continue
            await self.dp_repo.update(dp_id, status="needs_revision", review_comment=comment)
            await self._audit("data_point_revision_requested", dp_id, ctx, {"comment": comment})
            await self._notify_collector(dp, "needs_revision", ctx, comment)
            results.append({"id": dp_id, "success": True, "status": "needs_revision"})
        return {"results": results, "revision_count": sum(1 for r in results if r["success"])}
