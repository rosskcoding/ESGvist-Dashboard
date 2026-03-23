from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.assignment_sla import assignment_completed, assignment_matches_data_point, resolve_assignment_sla
from app.core.access import get_project_for_ctx
from app.core.dependencies import RequestContext
from app.db.models.completeness import RequirementItemStatus
from app.db.models.data_point import DataPoint
from app.db.models.project import MetricAssignment
from app.repositories.completeness_repo import CompletenessRepository


class DashboardService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.completeness_repo = CompletenessRepository(session)

    async def get_project_progress(self, project_id: int, ctx: RequestContext) -> dict:
        await get_project_for_ctx(self.session, project_id, ctx)

        status_q = (
            select(RequirementItemStatus.status, func.count())
            .where(RequirementItemStatus.reporting_project_id == project_id)
            .group_by(RequirementItemStatus.status)
        )
        result = await self.session.execute(status_q)
        status_counts = {row[0]: row[1] for row in result.all()}

        complete = status_counts.get("complete", 0)
        partial = status_counts.get("partial", 0)
        missing = status_counts.get("missing", 0)
        total = complete + partial + missing
        pct = round((complete / total * 100), 1) if total > 0 else 0

        dp_q = (
            select(DataPoint.status, func.count())
            .where(DataPoint.reporting_project_id == project_id)
            .group_by(DataPoint.status)
        )
        dp_result = await self.session.execute(dp_q)
        dp_counts = {row[0]: row[1] for row in dp_result.all()}

        standards = await self.completeness_repo.list_project_standards(project_id)
        standards_progress = []
        for standard_id, std_code, _std_name in standards:
            items_with_disclosures = await self.completeness_repo.list_project_items(project_id, standard_id)
            item_ids = [item.id for item, _disclosure in items_with_disclosures]
            item_statuses = await self.completeness_repo.list_project_item_statuses(project_id, item_ids)
            status_by_item_id = {status.requirement_item_id: status.status for status in item_statuses}

            standard_total = 0
            standard_complete = 0
            for item_id in item_ids:
                status = status_by_item_id.get(item_id, "missing")
                if status == "not_applicable":
                    continue
                standard_total += 1
                if status == "complete":
                    standard_complete += 1

            standard_pct = round((standard_complete / standard_total) * 100, 1) if standard_total else 0
            standards_progress.append({"standard_id": standard_id, "standard": std_code, "completion_percent": standard_pct})

        today = datetime.now(timezone.utc).date()
        assignments_result = await self.session.execute(
            select(MetricAssignment).where(MetricAssignment.reporting_project_id == project_id)
        )
        assignments = list(assignments_result.scalars().all())
        points_result = await self.session.execute(
            select(DataPoint).where(DataPoint.reporting_project_id == project_id)
        )
        data_points = list(points_result.scalars().all())

        sla_counts = {
            "on_track": 0,
            "warning": 0,
            "due_today": 0,
            "overdue": 0,
            "breach_level_1": 0,
            "breach_level_2": 0,
            "completed": 0,
            "no_deadline": 0,
        }
        breached_assignments = []
        overdue_count = 0

        for assignment in assignments:
            matching_points = [
                point for point in data_points if assignment_matches_data_point(assignment, point)
            ]
            sla_state = resolve_assignment_sla(
                deadline=assignment.deadline,
                escalation_after_days=assignment.escalation_after_days,
                completed=assignment_completed(assignment, matching_points),
                today=today,
            )
            sla_counts[sla_state.status] = sla_counts.get(sla_state.status, 0) + 1
            if sla_state.status in {"overdue", "breach_level_1", "breach_level_2"}:
                overdue_count += 1
            if sla_state.status in {"breach_level_1", "breach_level_2"}:
                breached_assignments.append(
                    {
                        "assignment_id": assignment.id,
                        "shared_element_id": assignment.shared_element_id,
                        "status": sla_state.status,
                        "days_overdue": sla_state.days_overdue,
                    }
                )

        return {
            "project_id": project_id,
            "overall_completion_percent": pct,
            "item_statuses": {
                "complete": complete,
                "partial": partial,
                "missing": missing,
                "total": total,
            },
            "data_point_statuses": dp_counts,
            "standards_progress": standards_progress,
            "overdue_assignments": overdue_count,
            "sla_counts": sla_counts,
            "breached_assignments": breached_assignments,
        }
