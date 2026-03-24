from collections import defaultdict
from datetime import date

import structlog
from sqlalchemy import select

from app.core.access import (
    assignment_matches_data_point,
    get_data_point_for_ctx,
    get_project_for_ctx,
    get_user_assignments,
)
from app.core.dashboard_cache import invalidate_dashboard_projects
from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.core.metrics import record_non_blocking_failure
from app.db.models.boundary import BoundaryMembership
from app.db.models.boundary_snapshot import BoundarySnapshot
from app.db.models.company_entity import CompanyEntity
from app.db.models.data_point import DataPoint, DataPointDimension
from app.db.models.evidence import DataPointEvidence, Evidence, EvidenceFile, EvidenceLink
from app.db.models.mapping import RequirementItemSharedElement
from app.db.models.project import MetricAssignment, ReportingProject, ReportingProjectStandard
from app.db.models.requirement_item import RequirementItem
from app.db.models.shared_element import SharedElement
from app.db.models.standard import DisclosureRequirement, Standard
from app.db.models.unit_reference import Methodology
from app.db.models.user import User
from app.repositories.audit_repo import AuditRepository
from app.repositories.data_point_repo import DataPointRepository
from app.repositories.notification_repo import NotificationRepository
from app.services.notification_service import NotificationService
from app.services.outlier_service import OutlierService

logger = structlog.get_logger("app.review")


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

    async def _audit(
        self, action: str, dp_id: int, ctx: RequestContext, changes: dict | None = None
    ):
        if self.audit_repo:
            await self.audit_repo.log(
                entity_type="DataPoint",
                entity_id=dp_id,
                action=action,
                user_id=ctx.user_id,
                organization_id=ctx.organization_id,
                changes=changes,
                performed_by_platform_admin=ctx.is_platform_admin,
            )

    async def _notify_collector(
        self, dp, action: str, ctx: RequestContext, comment: str | None = None
    ):
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
        except Exception:
            record_non_blocking_failure("review_service", "collector_notification")
            logger.warning(
                "review_collector_notification_failed",
                data_point_id=dp.id,
                collector_user_id=dp.created_by,
                action=action,
                organization_id=ctx.organization_id,
                triggered_by=ctx.user_id,
                exc_info=True,
            )

    def _require_review_access(self, ctx: RequestContext) -> None:
        if ctx.role not in ("reviewer", "admin", "esg_manager", "platform_admin"):
            raise AppError(
                "FORBIDDEN", 403, "Only reviewers or managers can perform review actions"
            )

    def _require_review_queue_access(self, ctx: RequestContext) -> None:
        if ctx.role not in ("reviewer", "auditor", "admin", "esg_manager", "platform_admin"):
            raise AppError(
                "FORBIDDEN", 403, "Only reviewers or auditors can access the review queue"
            )

    async def list_review_items(
        self,
        ctx: RequestContext,
        project_id: int | None = None,
        statuses: list[str] | None = None,
    ) -> dict:
        self._require_review_queue_access(ctx)
        allowed_statuses = statuses or ["submitted", "in_review"]

        assignments: list[MetricAssignment] = []
        projects: list[ReportingProject] = []

        if project_id is not None:
            project = await get_project_for_ctx(
                self.dp_repo.session,
                project_id,
                ctx,
                allow_collectors=False,
                allow_reviewers=True,
            )
            projects = [project]
            if ctx.role == "reviewer":
                assignments = await get_user_assignments(
                    self.dp_repo.session,
                    project_id,
                    ctx.user_id,
                    "reviewer",
                )
        elif ctx.role == "reviewer":
            assignment_result = await self.dp_repo.session.execute(
                select(MetricAssignment).where(MetricAssignment.reviewer_id == ctx.user_id)
            )
            assignments = list(assignment_result.scalars().all())
            project_ids = sorted({assignment.reporting_project_id for assignment in assignments})
            if not project_ids:
                return {"items": [], "total": 0}
            project_result = await self.dp_repo.session.execute(
                select(ReportingProject).where(ReportingProject.id.in_(project_ids))
            )
            projects = list(project_result.scalars().all())
        else:
            project_query = select(ReportingProject)
            if ctx.organization_id and not ctx.is_platform_admin:
                project_query = project_query.where(
                    ReportingProject.organization_id == ctx.organization_id
                )
            elif ctx.organization_id:
                project_query = project_query.where(
                    ReportingProject.organization_id == ctx.organization_id
                )
            project_result = await self.dp_repo.session.execute(project_query)
            projects = list(project_result.scalars().all())

        if not projects:
            return {"items": [], "total": 0}

        project_ids = [project.id for project in projects]
        dp_result = await self.dp_repo.session.execute(
            select(DataPoint)
            .where(
                DataPoint.reporting_project_id.in_(project_ids),
                DataPoint.status.in_(allowed_statuses),
            )
            .order_by(DataPoint.updated_at.desc(), DataPoint.id.desc())
        )
        data_points = list(dp_result.scalars().all())

        if ctx.role == "reviewer":
            data_points = [
                data_point
                for data_point in data_points
                if any(
                    assignment_matches_data_point(assignment, data_point)
                    for assignment in assignments
                )
            ]

        context = await self._load_review_context(data_points, projects)
        project_map = {project.id: project for project in projects}
        items = [
            self._serialize_review_item(
                data_point,
                project_map[data_point.reporting_project_id],
                context,
            )
            for data_point in data_points
        ]
        return {"items": items, "total": len(items)}

    async def _load_review_context(
        self,
        data_points: list[DataPoint],
        projects: list[ReportingProject],
    ) -> dict:
        if not data_points:
            return {
                "shared_elements": {},
                "user_names": {},
                "entities": {},
                "memberships": {},
                "standards": defaultdict(list),
                "methodologies": {},
                "dimensions": defaultdict(dict),
                "evidence": defaultdict(list),
                "assignments": defaultdict(list),
                "snapshots": {},
            }

        project_ids = [project.id for project in projects]
        project_map = {project.id: project for project in projects}
        shared_element_ids = sorted({dp.shared_element_id for dp in data_points})
        entity_ids = sorted(
            {
                entity_id
                for dp in data_points
                for entity_id in (dp.entity_id, dp.facility_id)
                if entity_id is not None
            }
        )
        user_ids = sorted({dp.created_by for dp in data_points if dp.created_by is not None})
        methodology_ids = sorted(
            {dp.methodology_id for dp in data_points if dp.methodology_id is not None}
        )
        boundary_ids = sorted(
            {
                project.boundary_definition_id
                for project in projects
                if project.boundary_definition_id is not None
            }
        )
        data_point_ids = [dp.id for dp in data_points]

        shared_elements: dict[int, SharedElement] = {}
        shared_result = await self.dp_repo.session.execute(
            select(SharedElement).where(SharedElement.id.in_(shared_element_ids))
        )
        shared_elements = {item.id: item for item in shared_result.scalars().all()}

        user_names: dict[int, str] = {}
        if user_ids:
            user_result = await self.dp_repo.session.execute(
                select(User.id, User.full_name).where(User.id.in_(user_ids))
            )
            user_names = {user_id: full_name for user_id, full_name in user_result.all()}

        entities: dict[int, str] = {}
        if entity_ids:
            entity_result = await self.dp_repo.session.execute(
                select(CompanyEntity.id, CompanyEntity.name).where(CompanyEntity.id.in_(entity_ids))
            )
            entities = {entity_id: name for entity_id, name in entity_result.all()}

        memberships: dict[tuple[int, int], dict[str, str | bool | None]] = {}
        if boundary_ids and entity_ids:
            membership_result = await self.dp_repo.session.execute(
                select(
                    BoundaryMembership.boundary_definition_id,
                    BoundaryMembership.entity_id,
                    BoundaryMembership.included,
                    BoundaryMembership.inclusion_reason,
                    BoundaryMembership.consolidation_method,
                ).where(
                    BoundaryMembership.boundary_definition_id.in_(boundary_ids),
                    BoundaryMembership.entity_id.in_(entity_ids),
                )
            )
            memberships = {
                (boundary_definition_id, entity_id): {
                    "included": included,
                    "inclusion_reason": inclusion_reason,
                    "consolidation_method": consolidation_method,
                }
                for (
                    boundary_definition_id,
                    entity_id,
                    included,
                    inclusion_reason,
                    consolidation_method,
                ) in membership_result.all()
            }

        standards: dict[tuple[int, int], list[dict[str, str]]] = defaultdict(list)
        standards_result = await self.dp_repo.session.execute(
            select(
                ReportingProjectStandard.reporting_project_id,
                RequirementItemSharedElement.shared_element_id,
                Standard.code,
                Standard.name,
            )
            .join(Standard, Standard.id == ReportingProjectStandard.standard_id)
            .join(DisclosureRequirement, DisclosureRequirement.standard_id == Standard.id)
            .join(
                RequirementItem,
                RequirementItem.disclosure_requirement_id == DisclosureRequirement.id,
            )
            .join(
                RequirementItemSharedElement,
                RequirementItemSharedElement.requirement_item_id == RequirementItem.id,
            )
            .where(
                ReportingProjectStandard.reporting_project_id.in_(project_ids),
                RequirementItemSharedElement.shared_element_id.in_(shared_element_ids),
            )
            .order_by(Standard.code, RequirementItem.id)
        )
        seen_standards: set[tuple[int, int, str]] = set()
        for project_id_value, shared_element_id, code, name in standards_result.all():
            key = (project_id_value, shared_element_id, code)
            if key in seen_standards:
                continue
            standards[(project_id_value, shared_element_id)].append({"code": code, "name": name})
            seen_standards.add(key)

        methodologies: dict[int, str] = {}
        if methodology_ids:
            methodology_result = await self.dp_repo.session.execute(
                select(Methodology.id, Methodology.name).where(Methodology.id.in_(methodology_ids))
            )
            methodologies = {
                methodology_id: name for methodology_id, name in methodology_result.all()
            }

        dimensions: dict[int, dict[str, str]] = defaultdict(dict)
        dimension_result = await self.dp_repo.session.execute(
            select(
                DataPointDimension.data_point_id,
                DataPointDimension.dimension_type,
                DataPointDimension.dimension_value,
            ).where(DataPointDimension.data_point_id.in_(data_point_ids))
        )
        for data_point_id, dimension_type, dimension_value in dimension_result.all():
            normalized = "gas_type" if dimension_type in {"gas", "gas_type"} else dimension_type
            dimensions[data_point_id][normalized] = dimension_value

        evidence: dict[int, list[dict[str, object | None]]] = defaultdict(list)
        evidence_result = await self.dp_repo.session.execute(
            select(
                DataPointEvidence.data_point_id,
                Evidence.id,
                Evidence.type,
                Evidence.title,
                EvidenceFile.file_name,
                EvidenceFile.file_uri,
                EvidenceLink.url,
            )
            .join(Evidence, Evidence.id == DataPointEvidence.evidence_id)
            .outerjoin(EvidenceFile, EvidenceFile.evidence_id == Evidence.id)
            .outerjoin(EvidenceLink, EvidenceLink.evidence_id == Evidence.id)
            .where(DataPointEvidence.data_point_id.in_(data_point_ids))
        )
        for (
            data_point_id,
            evidence_id,
            evidence_type,
            title,
            file_name,
            file_uri,
            url,
        ) in evidence_result.all():
            label = file_name or title
            evidence[data_point_id].append(
                {
                    "id": evidence_id,
                    "filename": label,
                    "url": file_uri or url,
                    "type": evidence_type,
                }
            )

        assignments: dict[int, list[MetricAssignment]] = defaultdict(list)
        assignment_result = await self.dp_repo.session.execute(
            select(MetricAssignment).where(MetricAssignment.reporting_project_id.in_(project_ids))
        )
        for assignment in assignment_result.scalars().all():
            assignments[assignment.reporting_project_id].append(assignment)

        snapshots: dict[int, str] = {}
        snapshot_result = await self.dp_repo.session.execute(
            select(BoundarySnapshot).where(BoundarySnapshot.reporting_project_id.in_(project_ids))
        )
        for snapshot in snapshot_result.scalars().all():
            project = project_map.get(snapshot.reporting_project_id)
            if project and snapshot.boundary_definition_id == project.boundary_definition_id:
                snapshots[snapshot.reporting_project_id] = f"Snapshot #{snapshot.id}"
            else:
                snapshots[snapshot.reporting_project_id] = "Outdated snapshot"

        # Outlier detection
        outlier_svc = OutlierService(self.dp_repo.session)
        outliers = await outlier_svc.check_outliers_batch(data_points)

        return {
            "shared_elements": shared_elements,
            "user_names": user_names,
            "entities": entities,
            "memberships": memberships,
            "standards": standards,
            "methodologies": methodologies,
            "dimensions": dimensions,
            "evidence": evidence,
            "assignments": assignments,
            "snapshots": snapshots,
            "outliers": outliers,
        }

    def _serialize_review_item(
        self,
        data_point: DataPoint,
        project: ReportingProject,
        context: dict,
    ) -> dict:
        shared_element = context["shared_elements"].get(data_point.shared_element_id)
        standards = context["standards"].get((project.id, data_point.shared_element_id), [])
        primary_standard = (
            standards[0] if standards else {"code": "CUSTOM", "name": "Custom disclosure"}
        )

        scope_entity_id = data_point.facility_id or data_point.entity_id
        membership = None
        if project.boundary_definition_id is not None and scope_entity_id is not None:
            membership = context["memberships"].get(
                (project.boundary_definition_id, scope_entity_id)
            )

        if membership is not None:
            inclusion_status = "included" if membership["included"] else "excluded"
            inclusion_reason = membership["inclusion_reason"] or "Boundary membership rule"
            consolidation_method = membership["consolidation_method"] or "full"
        elif scope_entity_id is None:
            inclusion_status = "included"
            inclusion_reason = "Project-level data point"
            consolidation_method = "full"
        elif project.boundary_definition_id is None:
            inclusion_status = "included"
            inclusion_reason = "No active boundary applied"
            consolidation_method = "full"
        else:
            inclusion_status = "partial"
            inclusion_reason = "No explicit membership found in active boundary"
            consolidation_method = "full"

        from app.services.outlier_service import OutlierResult

        outlier = context.get("outliers", {}).get(data_point.id, OutlierResult())

        assignment = self._pick_assignment(
            data_point,
            context["assignments"].get(project.id, []),
        )
        urgency, is_overdue = self._compute_urgency(
            assignment.deadline if assignment else None, data_point.status
        )
        submitted_at = data_point.updated_at or data_point.created_at
        dimensions = context["dimensions"].get(data_point.id, {})

        return {
            "id": data_point.id,
            "project_id": project.id,
            "project_name": project.name,
            "element_name": shared_element.name
            if shared_element
            else f"Element #{data_point.shared_element_id}",
            "element_code": shared_element.code
            if shared_element
            else f"SE-{data_point.shared_element_id}",
            "submitter_name": context["user_names"].get(data_point.created_by, "Unknown user"),
            "submitted_at": submitted_at.isoformat() if submitted_at else None,
            "status": data_point.status,
            "urgency": urgency,
            "is_outlier": outlier.is_outlier,
            "outlier_reason": outlier.reason,
            "is_overdue": is_overdue,
            "entity_name": context["entities"].get(data_point.entity_id),
            "standard_code": primary_standard["code"],
            "standard_name": primary_standard["name"],
            "value": self._format_value(data_point),
            "unit": data_point.unit_code or "",
            "methodology": context["methodologies"].get(data_point.methodology_id, "Not specified"),
            "narrative": data_point.text_value or "",
            "previous_value": str(outlier.previous_value)
            if outlier.previous_value is not None
            else None,
            "previous_unit": outlier.previous_unit,
            "dimensions": {
                "scope": dimensions.get("scope"),
                "gas_type": dimensions.get("gas_type"),
                "category": dimensions.get("category"),
            },
            "evidence": context["evidence"].get(data_point.id, []),
            "boundary_context": {
                "entity_name": context["entities"].get(scope_entity_id),
                "inclusion_status": inclusion_status,
                "inclusion_reason": inclusion_reason,
                "consolidation_method": consolidation_method,
                "snapshot_version": context["snapshots"].get(project.id, "No snapshot"),
            },
        }

    @staticmethod
    def _pick_assignment(
        data_point: DataPoint,
        assignments: list[MetricAssignment],
    ) -> MetricAssignment | None:
        matches = [
            assignment
            for assignment in assignments
            if assignment_matches_data_point(assignment, data_point)
        ]
        if not matches:
            return None
        return sorted(
            matches,
            key=lambda assignment: (
                assignment.facility_id is None,
                assignment.entity_id is None,
                assignment.id,
            ),
        )[0]

    @staticmethod
    def _compute_urgency(deadline, status: str) -> tuple[str, bool]:
        if deadline is not None:
            days_until_deadline = (deadline - date.today()).days
            if days_until_deadline < 0:
                return "critical", True
            if days_until_deadline <= 2:
                return "high", False
            if days_until_deadline <= 5:
                return "medium", False

        if status == "submitted":
            return "high", False
        if status == "in_review":
            return "medium", False
        return "low", False

    @staticmethod
    def _format_value(data_point: DataPoint) -> str:
        if data_point.numeric_value is not None:
            return f"{float(data_point.numeric_value):g}"
        if data_point.text_value:
            return data_point.text_value
        return "-"

    async def batch_approve(
        self, dp_ids: list[int], comment: str | None, ctx: RequestContext
    ) -> dict:
        self._require_review_access(ctx)
        results = []
        affected_project_ids: set[int] = set()
        for dp_id in dp_ids:
            dp, _, _ = await get_data_point_for_ctx(self.dp_repo.session, dp_id, ctx)
            if dp.status != "in_review":
                results.append(
                    {
                        "id": dp_id,
                        "success": False,
                        "reason": f"Status is '{dp.status}', expected 'in_review'",
                    }
                )
                continue
            await self.dp_repo.update(dp_id, status="approved", review_comment=comment)
            await self._audit("data_point_approved", dp_id, ctx, {"comment": comment})
            await self._notify_collector(dp, "approved", ctx, comment)
            affected_project_ids.add(dp.reporting_project_id)
            results.append({"id": dp_id, "success": True, "status": "approved"})
        await invalidate_dashboard_projects(affected_project_ids)
        return {"results": results, "approved_count": sum(1 for r in results if r["success"])}

    async def batch_reject(
        self, dp_ids: list[int], comment: str | None, ctx: RequestContext
    ) -> dict:
        self._require_review_access(ctx)
        if not comment:
            raise AppError("REVIEW_COMMENT_REQUIRED", 422, "Comment is required for batch reject")

        results = []
        affected_project_ids: set[int] = set()
        for dp_id in dp_ids:
            dp, _, _ = await get_data_point_for_ctx(self.dp_repo.session, dp_id, ctx)
            if dp.status != "in_review":
                results.append(
                    {"id": dp_id, "success": False, "reason": f"Status is '{dp.status}'"}
                )
                continue
            await self.dp_repo.update(dp_id, status="rejected", review_comment=comment)
            await self._audit(
                "data_point_rejected",
                dp_id,
                ctx,
                {"comment": comment, "reason_code": "reviewer_rejection"},
            )
            await self._notify_collector(dp, "rejected", ctx, comment)
            affected_project_ids.add(dp.reporting_project_id)
            results.append({"id": dp_id, "success": True, "status": "rejected"})
        await invalidate_dashboard_projects(affected_project_ids)
        return {"results": results, "rejected_count": sum(1 for r in results if r["success"])}

    async def batch_request_revision(
        self, dp_ids: list[int], comment: str | None, ctx: RequestContext
    ) -> dict:
        self._require_review_access(ctx)
        if not comment:
            raise AppError(
                "REVIEW_COMMENT_REQUIRED", 422, "Comment is required for request revision"
            )

        results = []
        affected_project_ids: set[int] = set()
        for dp_id in dp_ids:
            dp, _, _ = await get_data_point_for_ctx(self.dp_repo.session, dp_id, ctx)
            if dp.status != "in_review":
                results.append(
                    {"id": dp_id, "success": False, "reason": f"Status is '{dp.status}'"}
                )
                continue
            await self.dp_repo.update(dp_id, status="needs_revision", review_comment=comment)
            await self._audit("data_point_revision_requested", dp_id, ctx, {"comment": comment})
            await self._notify_collector(dp, "needs_revision", ctx, comment)
            affected_project_ids.add(dp.reporting_project_id)
            results.append({"id": dp_id, "success": True, "status": "needs_revision"})
        await invalidate_dashboard_projects(affected_project_ids)
        return {"results": results, "revision_count": sum(1 for r in results if r["success"])}
