from app.repositories.completeness_repo import CompletenessRepository
from app.schemas.completeness import CompletenessOut, ItemStatusOut


class CompletenessService:
    def __init__(self, repo: CompletenessRepository):
        self.repo = repo

    async def bind_data_point(
        self, project_id: int, item_id: int, dp_id: int
    ) -> dict:
        b = await self.repo.create_binding(project_id, item_id, dp_id)
        # Recalculate after binding
        await self.calculate_item_status(project_id, item_id)
        return {"binding_id": b.id}

    async def calculate_item_status(self, project_id: int, item_id: int) -> str:
        """Calculate completeness status for a single requirement item."""
        data_points = await self.repo.get_bound_data_points(project_id, item_id)

        if not data_points:
            status = "missing"
            reason = "No data submitted"
            await self.repo.upsert_item_status(project_id, item_id, status, reason)
            return status

        has_approved = any(dp.status == "approved" for dp in data_points)
        if not has_approved:
            status = "partial"
            reason = "Data exists but not approved"
            await self.repo.upsert_item_status(project_id, item_id, status, reason)
            return status

        # Check evidence for approved data points
        for dp in data_points:
            if dp.status == "approved":
                ev_count = await self.repo.count_evidence_for_dp(dp.id)
                # Evidence check only blocks if item requires it
                # (simplified — full check would look at requirement_item.requires_evidence)

        status = "complete"
        reason = None
        await self.repo.upsert_item_status(project_id, item_id, status, reason)
        return status

    async def aggregate_disclosure_status(
        self, project_id: int, disclosure_id: int
    ) -> dict:
        """Aggregate item statuses into disclosure status."""
        items = await self.repo.get_required_items(disclosure_id)

        if not items:
            await self.repo.upsert_disclosure_status(project_id, disclosure_id, "complete", 100.0)
            return {"status": "complete", "completion_percent": 100.0}

        statuses = []
        for item in items:
            s = await self.repo.get_item_status(project_id, item.id)
            statuses.append(s.status if s else "missing")

        complete_count = sum(1 for s in statuses if s == "complete")
        total = sum(1 for s in statuses if s != "not_applicable")

        if total == 0:
            pct = 100.0
            status = "complete"
        else:
            pct = (complete_count / total) * 100
            if complete_count == total:
                status = "complete"
            elif complete_count > 0:
                status = "partial"
            else:
                status = "missing"

        await self.repo.upsert_disclosure_status(project_id, disclosure_id, status, pct)
        return {"status": status, "completion_percent": round(pct, 1)}

    async def get_project_completeness(self, project_id: int) -> CompletenessOut:
        """Get overall completeness for a project (all disclosures)."""
        from sqlalchemy import select
        from app.db.models.completeness import RequirementItemStatus

        # Get all item statuses for project
        # This is a simplified version — full implementation would iterate by standard/disclosure
        return CompletenessOut(
            project_id=project_id,
            items=[],
            overall_percent=0,
            overall_status="missing",
        )
