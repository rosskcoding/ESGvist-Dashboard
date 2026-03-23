from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import get_project_for_ctx
from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.db.models.boundary import BoundaryDefinition, BoundaryMembership
from app.db.models.boundary_snapshot import BoundarySnapshot
from app.db.models.company_entity import CompanyEntity
from app.db.models.completeness import DisclosureRequirementStatus, RequirementItemStatus
from app.db.models.data_point import DataPoint
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

    async def _get_boundary_validation(self, project: ReportingProject) -> dict | None:
        if not project.boundary_definition_id:
            return None

        boundary_result = await self.session.execute(
            select(BoundaryDefinition).where(BoundaryDefinition.id == project.boundary_definition_id)
        )
        boundary = boundary_result.scalar_one_or_none()
        if not boundary:
            return None

        default_boundary_result = await self.session.execute(
            select(BoundaryDefinition.id).where(
                BoundaryDefinition.organization_id == project.organization_id,
                BoundaryDefinition.is_default == True,
            )
        )
        default_boundary_id = default_boundary_result.scalar_one_or_none()

        snapshot_result = await self.session.execute(
            select(BoundarySnapshot).where(BoundarySnapshot.reporting_project_id == project.id)
        )
        snapshot = snapshot_result.scalar_one_or_none()
        snapshot_locked = (
            snapshot is not None
            and snapshot.boundary_definition_id == project.boundary_definition_id
        )

        memberships = (
            await self.session.execute(
                select(BoundaryMembership).where(
                    BoundaryMembership.boundary_definition_id == project.boundary_definition_id,
                    BoundaryMembership.included == True,
                )
            )
        ).scalars().all()
        entity_ids = sorted({membership.entity_id for membership in memberships})
        entity_names = {}
        if entity_ids:
            entity_result = await self.session.execute(
                select(CompanyEntity).where(CompanyEntity.id.in_(entity_ids))
            )
            entity_names = {entity.id: entity.name for entity in entity_result.scalars().all()}

        data_points_result = await self.session.execute(
            select(DataPoint).where(DataPoint.reporting_project_id == project.id)
        )
        covered_entity_ids = set()
        for data_point in data_points_result.scalars().all():
            scope_entity_id = data_point.facility_id or data_point.entity_id
            if scope_entity_id in entity_ids:
                covered_entity_ids.add(scope_entity_id)

        entities_without_data = [
            entity_names[entity_id]
            for entity_id in entity_ids
            if entity_id not in covered_entity_ids and entity_id in entity_names
        ]

        return {
            "selected_boundary": boundary.name,
            "snapshot_locked": snapshot_locked,
            "entities_in_scope": len(entity_ids),
            "manual_overrides": sum(1 for membership in memberships if membership.inclusion_source == "manual"),
            "unresolved_structure_issues": 0,
            "boundary_differs_from_default": bool(
                default_boundary_id and default_boundary_id != project.boundary_definition_id
            ),
            "entities_without_data": entities_without_data,
        }

    async def readiness_check(self, project_id: int, ctx: RequestContext | None = None) -> dict:
        if ctx:
            if ctx.role not in ("admin", "esg_manager", "platform_admin", "auditor"):
                raise AppError("FORBIDDEN", 403, "You don't have permission to view export readiness")
            project = await get_project_for_ctx(
                self.session,
                project_id,
                ctx,
                allow_collectors=False,
                allow_reviewers=False,
            )
        else:
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

        snapshot_result = await self.session.execute(
            select(BoundarySnapshot).where(BoundarySnapshot.reporting_project_id == project_id)
        )
        snapshot = snapshot_result.scalar_one_or_none()
        boundary_locked = (
            project.boundary_definition_id is not None
            and snapshot is not None
            and snapshot.boundary_definition_id == project.boundary_definition_id
        )

        blocking = missing + (0 if boundary_locked else 1)
        warnings = partial  # partial items are warnings

        overall_pct = (complete / total * 100) if total > 0 else 0

        # Boundary metadata
        boundary_meta = await self._get_boundary_metadata(project)
        boundary_validation = await self._get_boundary_validation(project)
        blocking_issue_details = []
        warning_details = []
        if missing:
            blocking_issue_details.append(
                {
                    "code": "MISSING_REQUIRED_ITEMS",
                    "message": f"{missing} required items are still missing",
                    "count": missing,
                }
            )
        if not boundary_locked:
            blocking_issue_details.append(
                {
                    "code": "BOUNDARY_SNAPSHOT_REQUIRED",
                    "message": "Boundary snapshot must be created and match the active boundary",
                    "count": 1,
                }
            )
        if partial:
            warning_details.append(
                {
                    "code": "PARTIAL_ITEMS",
                    "message": f"{partial} items are partially complete",
                    "count": partial,
                }
            )
        if boundary_validation and boundary_validation["entities_without_data"]:
            warning_details.append(
                {
                    "code": "BOUNDARY_ENTITIES_WITHOUT_DATA",
                    "message": "Some entities in boundary do not have project data yet",
                    "count": len(boundary_validation["entities_without_data"]),
                }
            )

        return {
            "project_id": project_id,
            "ready": blocking == 0,
            "overall_ready": blocking == 0,
            "completion_percent": round(overall_pct, 1),
            "total_items": total,
            "complete": complete,
            "partial": partial,
            "missing": missing,
            "blocking_issues": blocking,
            "warnings": warnings,
            "blocking_issue_details": blocking_issue_details,
            "warning_details": warning_details,
            "boundary_locked": boundary_locked,
            "boundary_validation": boundary_validation,
            **boundary_meta,
        }

    async def export_data(self, project_id: int, ctx: RequestContext | None = None) -> dict:
        """Export project data with boundary metadata."""
        if ctx:
            project = await get_project_for_ctx(
                self.session,
                project_id,
                ctx,
                allow_collectors=False,
                allow_reviewers=False,
            )
        else:
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

    async def publish(self, project_id: int, ctx: RequestContext | None = None) -> dict:
        if ctx:
            if ctx.role not in ("admin", "esg_manager", "platform_admin"):
                raise AppError("FORBIDDEN", 403, "Only admin or ESG manager can publish projects")
            project = await get_project_for_ctx(
                self.session,
                project_id,
                ctx,
                allow_collectors=False,
                allow_reviewers=False,
            )
        else:
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
