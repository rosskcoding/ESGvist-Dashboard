from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.db.models.boundary import BoundaryDefinition, BoundaryMembership
from app.db.models.boundary_snapshot import BoundarySnapshot
from app.db.models.completeness import DisclosureRequirementStatus, RequirementItemStatus
from app.db.models.project import ReportingProject


class ExportService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _get_boundary_metadata(self, project: ReportingProject) -> dict:
        """Gather boundary metadata for a project."""
        boundary_type = None
        snapshot_id = None
        snapshot_date = None
        entities_in_scope = 0
        manual_overrides = 0

        if project.boundary_definition_id:
            # Get boundary definition
            bd_result = await self.session.execute(
                select(BoundaryDefinition).where(
                    BoundaryDefinition.id == project.boundary_definition_id
                )
            )
            boundary_def = bd_result.scalar_one_or_none()
            if boundary_def:
                boundary_type = boundary_def.boundary_type

            # Count entities in scope
            entity_count_q = select(func.count()).select_from(BoundaryMembership).where(
                BoundaryMembership.boundary_definition_id == project.boundary_definition_id,
                BoundaryMembership.included == True,
            )
            entities_in_scope = (await self.session.execute(entity_count_q)).scalar_one()

            # Count manual overrides
            override_count_q = select(func.count()).select_from(BoundaryMembership).where(
                BoundaryMembership.boundary_definition_id == project.boundary_definition_id,
                BoundaryMembership.inclusion_source == "manual",
            )
            manual_overrides = (await self.session.execute(override_count_q)).scalar_one()

        # Get snapshot info
        snap_result = await self.session.execute(
            select(BoundarySnapshot).where(
                BoundarySnapshot.reporting_project_id == project.id
            )
        )
        snapshot = snap_result.scalar_one_or_none()
        if snapshot:
            snapshot_id = snapshot.id
            snapshot_date = snapshot.created_at.isoformat() if snapshot.created_at else None

        return {
            "boundary_type": boundary_type,
            "snapshot_id": snapshot_id,
            "snapshot_date": snapshot_date,
            "entities_in_scope": entities_in_scope,
            "manual_overrides": manual_overrides,
        }

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

        # Boundary metadata
        boundary_meta = await self._get_boundary_metadata(project)

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
            **boundary_meta,
        }

    async def export_data(self, project_id: int) -> dict:
        """Export project data with boundary metadata."""
        proj = await self.session.execute(
            select(ReportingProject).where(ReportingProject.id == project_id)
        )
        project = proj.scalar_one_or_none()
        if not project:
            raise AppError("NOT_FOUND", 404, f"Project {project_id} not found")

        boundary_meta = await self._get_boundary_metadata(project)

        return {
            "project_id": project_id,
            "project_name": project.name,
            "status": project.status,
            "reporting_year": project.reporting_year,
            "boundary": boundary_meta,
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
