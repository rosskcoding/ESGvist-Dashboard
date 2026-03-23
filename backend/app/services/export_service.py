from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.db.models.completeness import DisclosureRequirementStatus, RequirementItemStatus
from app.db.models.project import ReportingProject


class ExportService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def readiness_check(self, project_id: int) -> dict:
        proj = await self.session.execute(
            select(ReportingProject).where(ReportingProject.id == project_id)
        )
        project = proj.scalar_one_or_none()
        if not project:
            raise AppError("NOT_FOUND", 404, f"Project {project_id} not found")

        # Count item statuses
        statuses_q = select(RequirementItemStatus.status, func.count()).where(
            RequirementItemStatus.reporting_project_id == project_id
        ).group_by(RequirementItemStatus.status)
        result = await self.session.execute(statuses_q)
        status_counts = {row[0]: row[1] for row in result.all()}

        complete = status_counts.get("complete", 0)
        partial = status_counts.get("partial", 0)
        missing = status_counts.get("missing", 0)
        total = complete + partial + missing

        blocking = missing  # missing mandatory items block export
        warnings = partial  # partial items are warnings

        overall_pct = (complete / total * 100) if total > 0 else 0

        return {
            "project_id": project_id,
            "ready": blocking == 0,
            "completion_percent": round(overall_pct, 1),
            "total_items": total,
            "complete": complete,
            "partial": partial,
            "missing": missing,
            "blocking_issues": blocking,
            "warnings": warnings,
            "boundary_locked": project.boundary_definition_id is not None,
        }

    async def publish(self, project_id: int) -> dict:
        proj = await self.session.execute(
            select(ReportingProject).where(ReportingProject.id == project_id)
        )
        project = proj.scalar_one_or_none()
        if not project:
            raise AppError("NOT_FOUND", 404, f"Project {project_id} not found")

        if project.status == "published":
            raise AppError("CONFLICT", 409, "Project already published")

        project.status = "published"
        await self.session.flush()

        return {"project_id": project_id, "status": "published"}
