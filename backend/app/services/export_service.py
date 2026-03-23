import csv
import hashlib
import json
from datetime import datetime, timezone
from io import StringIO

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
from app.db.models.export_job import ExportJob
from app.db.models.project import ReportingProject
from app.repositories.audit_repo import AuditRepository
from app.repositories.export_repo import ExportRepository
from app.schemas.export import ExportArtifactOut, ExportJobCreate, ExportJobListOut, ExportJobOut


class ExportService:
    def __init__(
        self,
        session: AsyncSession,
        repo: ExportRepository | None = None,
        audit_repo: AuditRepository | None = None,
    ):
        self.session = session
        self.repo = repo or ExportRepository(session)
        self.audit_repo = audit_repo

    @staticmethod
    def _require_export_admin(ctx: RequestContext) -> None:
        if ctx.role not in ("admin", "esg_manager", "platform_admin"):
            raise AppError("FORBIDDEN", 403, "Only admin or ESG manager can queue export jobs")

    @staticmethod
    def _require_export_reader(ctx: RequestContext) -> None:
        if ctx.role not in ("admin", "esg_manager", "platform_admin", "auditor"):
            raise AppError("FORBIDDEN", 403, "You don't have permission to access export jobs")

    @staticmethod
    def _serialize_job(job: ExportJob) -> ExportJobOut:
        return ExportJobOut(
            id=job.id,
            organization_id=job.organization_id,
            reporting_project_id=job.reporting_project_id,
            requested_by_user_id=job.requested_by_user_id,
            report_type=job.report_type,
            export_format=job.export_format,
            status=job.status,
            content_type=job.content_type,
            artifact_name=job.artifact_name,
            artifact_size_bytes=job.artifact_size_bytes,
            checksum=job.checksum,
            error_message=job.error_message,
            created_at=job.created_at,
            updated_at=job.updated_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
        )

    async def _audit(
        self,
        *,
        action: str,
        job: ExportJob | None = None,
        ctx: RequestContext | None = None,
        changes: dict | None = None,
    ) -> None:
        if not self.audit_repo:
            return
        await self.audit_repo.log(
            entity_type="ExportJob",
            entity_id=job.id if job else None,
            action=action,
            user_id=ctx.user_id if ctx else (job.requested_by_user_id if job else None),
            organization_id=job.organization_id if job else (ctx.organization_id if ctx else None),
            changes=changes,
            performed_by_platform_admin=bool(ctx and ctx.is_platform_admin),
        )

    async def _get_job_for_ctx(self, job_id: int, ctx: RequestContext) -> ExportJob:
        self._require_export_reader(ctx)
        job = await self.repo.get_job_or_raise(job_id)
        await get_project_for_ctx(
            self.session,
            job.reporting_project_id,
            ctx,
            allow_collectors=False,
            allow_reviewers=False,
        )
        return job

    @staticmethod
    def _build_csv_artifact(payload: dict) -> str:
        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["field", "value"])
        writer.writerow(["project_id", payload["project"]["id"]])
        writer.writerow(["project_name", payload["project"]["name"]])
        writer.writerow(["project_status", payload["project"]["status"]])
        writer.writerow(["reporting_year", payload["project"]["reporting_year"] or ""])
        writer.writerow(["completion_percent", payload["readiness"]["completion_percent"]])
        writer.writerow(["ready", str(payload["readiness"]["ready"]).lower()])
        writer.writerow(["total_items", payload["readiness"]["total_items"]])
        writer.writerow(["complete_items", payload["readiness"]["complete"]])
        writer.writerow(["partial_items", payload["readiness"]["partial"]])
        writer.writerow(["missing_items", payload["readiness"]["missing"]])
        writer.writerow(["blocking_issues", payload["readiness"]["blocking_issues"]])
        writer.writerow(["warnings", payload["readiness"]["warnings"]])
        writer.writerow(["boundary_type", payload["boundary"].get("boundary_type") or ""])
        writer.writerow(["entities_in_scope", payload["boundary"].get("entities_in_scope", 0)])
        return buffer.getvalue()

    async def _build_export_payload(self, project_id: int) -> dict:
        export_data = await self.export_data(project_id)
        readiness = await self.readiness_check(project_id)
        return {
            "project": {
                "id": export_data["project_id"],
                "name": export_data["project_name"],
                "status": export_data["status"],
                "reporting_year": export_data["reporting_year"],
            },
            "boundary": export_data["boundary"],
            "readiness": readiness,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def queue_export_job(
        self,
        project_id: int,
        payload: ExportJobCreate,
        ctx: RequestContext,
    ) -> ExportJobOut:
        self._require_export_admin(ctx)
        project = await get_project_for_ctx(
            self.session,
            project_id,
            ctx,
            allow_collectors=False,
            allow_reviewers=False,
        )
        job = await self.repo.create_job(
            organization_id=project.organization_id,
            reporting_project_id=project.id,
            requested_by_user_id=ctx.user_id,
            report_type=payload.report_type,
            export_format=payload.export_format,
            status="queued",
        )
        await self._audit(
            action="export_job_queued",
            job=job,
            ctx=ctx,
            changes={"export_format": payload.export_format, "report_type": payload.report_type},
        )
        return self._serialize_job(job)

    async def list_export_jobs(
        self,
        project_id: int,
        ctx: RequestContext,
        page: int = 1,
        page_size: int = 20,
    ) -> ExportJobListOut:
        self._require_export_reader(ctx)
        project = await get_project_for_ctx(
            self.session,
            project_id,
            ctx,
            allow_collectors=False,
            allow_reviewers=False,
        )
        jobs, total = await self.repo.list_project_jobs(project.organization_id, project.id, page, page_size)
        return ExportJobListOut(items=[self._serialize_job(job) for job in jobs], total=total)

    async def get_export_job(self, job_id: int, ctx: RequestContext) -> ExportJobOut:
        job = await self._get_job_for_ctx(job_id, ctx)
        return self._serialize_job(job)

    async def get_export_artifact(self, job_id: int, ctx: RequestContext) -> ExportArtifactOut:
        job = await self._get_job_for_ctx(job_id, ctx)
        if job.status != "completed" or not job.artifact_body or not job.content_type or not job.artifact_name:
            raise AppError("EXPORT_ARTIFACT_NOT_READY", 409, "Export artifact is not ready yet")
        if job.export_format == "json":
            content: dict | str = json.loads(job.artifact_body)
        else:
            content = job.artifact_body
        return ExportArtifactOut(
            job_id=job.id,
            export_format=job.export_format,
            content_type=job.content_type,
            artifact_name=job.artifact_name,
            content=content,
            checksum=job.checksum,
        )

    async def process_queued_jobs(self, limit: int = 25) -> dict:
        jobs = await self.repo.list_queued_jobs(limit=limit)
        result = {"checked": len(jobs), "processed": 0, "completed": 0, "failed": 0}

        for job in jobs:
            result["processed"] += 1
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            job.error_message = None
            await self.session.flush()
            try:
                payload = await self._build_export_payload(job.reporting_project_id)
                if job.report_type == "readiness_snapshot":
                    payload = {
                        "project": payload["project"],
                        "readiness": payload["readiness"],
                        "generated_at": payload["generated_at"],
                    }

                if job.export_format == "json":
                    artifact_body = json.dumps(payload, indent=2, sort_keys=True)
                    content_type = "application/json"
                else:
                    artifact_body = self._build_csv_artifact(payload)
                    content_type = "text/csv"

                job.status = "completed"
                job.completed_at = datetime.now(timezone.utc)
                job.content_type = content_type
                job.artifact_body = artifact_body
                job.artifact_size_bytes = len(artifact_body.encode("utf-8"))
                job.checksum = hashlib.sha256(artifact_body.encode("utf-8")).hexdigest()
                job.artifact_name = (
                    f"project-{job.reporting_project_id}-export-{job.id}.{job.export_format}"
                )
                await self.session.flush()
                await self._audit(
                    action="export_job_completed",
                    job=job,
                    changes={
                        "artifact_name": job.artifact_name,
                        "export_format": job.export_format,
                        "report_type": job.report_type,
                    },
                )
                result["completed"] += 1
            except Exception as exc:
                job.status = "failed"
                job.error_message = str(exc)
                job.completed_at = datetime.now(timezone.utc)
                await self.session.flush()
                await self._audit(
                    action="export_job_failed",
                    job=job,
                    changes={"error_message": job.error_message},
                )
                result["failed"] += 1
        return result

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
