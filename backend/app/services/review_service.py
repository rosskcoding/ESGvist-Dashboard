from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.repositories.data_point_repo import DataPointRepository


class ReviewService:
    def __init__(self, dp_repo: DataPointRepository):
        self.dp_repo = dp_repo

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
            results.append({"id": dp_id, "success": True, "status": "rejected"})
        return {"results": results, "rejected_count": sum(1 for r in results if r["success"])}
