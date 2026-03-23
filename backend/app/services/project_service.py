from datetime import date

from sqlalchemy import delete, func, select

from app.core.assignment_sla import (
    assignment_completed,
    assignment_matches_data_point,
    resolve_assignment_sla,
)
from app.core.access import get_project_for_ctx, get_user_assignments, user_has_project_assignment
from app.core.dependencies import RequestContext
from app.core.exceptions import AppError, GateBlockedError
from app.db.models.boundary import BoundaryMembership
from app.db.models.company_entity import CompanyEntity
from app.db.models.completeness import RequirementItemStatus
from app.db.models.data_point import DataPoint
from app.db.models.boundary_snapshot import BoundarySnapshot
from app.db.models.project import MetricAssignment, ReportingProject, ReportingProjectStandard
from app.db.models.role_binding import RoleBinding
from app.db.models.shared_element import SharedElement
from app.db.models.standard import DisclosureRequirement, Standard
from app.db.models.user import User
from app.events.bus import (
    AssignmentCreated,
    AssignmentUpdated,
    BoundaryAppliedToProject,
    ProjectPublished,
    ProjectReviewStarted,
    ProjectStarted,
    get_event_bus,
)
from app.policies.auth_policy import AuthPolicy
from app.repositories.audit_repo import AuditRepository
from app.repositories.completeness_repo import CompletenessRepository
from app.repositories.project_repo import ProjectRepository
from app.schemas.projects import (
    ProjectAssignmentSummaryListOut,
    ProjectAssignmentSummaryOut,
    AssignmentBulkUpdate,
    AssignmentCreate,
    AssignmentInlineUpdate,
    AssignmentMatrixEntityOut,
    AssignmentMatrixOut,
    AssignmentMatrixRowOut,
    AssignmentMatrixUserOut,
    AssignmentOut,
    BoundaryDefCreate,
    BoundaryDefOut,
    ProjectCreate,
    ProjectListOut,
    ProjectOut,
    ProjectStandardSummaryListOut,
    ProjectStandardSummaryOut,
    ProjectStandardAdd,
)
from app.workflows.gates.base import GateEngine
from app.workflows.gates.boundary_gate import BoundaryNotDefinedGate, BoundaryNotLockedGate
from app.workflows.gates.completeness_gate import ProjectIncompleteGate
from app.workflows.gates.review_gate import NoRequirementsGate, ReviewNotCompletedGate, UnresolvedReviewGate


class ProjectService:
    def __init__(self, repo: ProjectRepository, audit_repo: AuditRepository | None = None):
        self.repo = repo
        self.audit_repo = audit_repo
        self.completeness_repo = CompletenessRepository(repo.session)
        self.project_gate_engine = GateEngine(
            [
                NoRequirementsGate(),
                BoundaryNotDefinedGate(),
                BoundaryNotLockedGate(),
                ProjectIncompleteGate(),
                ReviewNotCompletedGate(),
                UnresolvedReviewGate(),
            ]
        )

    async def _audit(self, entity_type: str, action: str, ctx: RequestContext,
                     entity_id: int | None = None, changes: dict | None = None):
        if self.audit_repo:
            await self.audit_repo.log(
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                user_id=ctx.user_id,
                organization_id=ctx.organization_id,
                changes=changes,
                performed_by_platform_admin=ctx.is_platform_admin,
            )

    def _require_manager(self, ctx: RequestContext) -> None:
        if ctx.role not in ("admin", "esg_manager", "platform_admin"):
            raise AppError("FORBIDDEN", 403, "Only admin/esg_manager can manage projects")

    async def _project_completion_percentage(self, project_id: int) -> float:
        items_with_disclosures = await self.completeness_repo.list_project_items(project_id)
        item_ids = [item.id for item, _disclosure in items_with_disclosures]
        statuses = await self.completeness_repo.list_project_item_statuses(project_id, item_ids)
        status_by_item = {status.requirement_item_id: status.status for status in statuses}

        complete = partial = missing = 0
        for item_id in item_ids:
            status = status_by_item.get(item_id, "missing")
            if status == "not_applicable":
                continue
            if status == "complete":
                complete += 1
            elif status == "partial":
                partial += 1
            else:
                missing += 1
        total = complete + partial + missing
        return round((complete / total) * 100, 1) if total else 0.0

    async def _build_project_out(self, project: ReportingProject) -> ProjectOut:
        standards = await self.completeness_repo.list_project_standards(project.id)
        return ProjectOut.model_validate(
            {
                "id": project.id,
                "organization_id": project.organization_id,
                "name": project.name,
                "status": project.status,
                "reporting_year": project.reporting_year,
                "deadline": project.deadline,
                "boundary_definition_id": project.boundary_definition_id,
                "created_at": project.created_at,
                "updated_at": project.updated_at,
                "reporting_period_start": None,
                "reporting_period_end": None,
                "standard_codes": [code for _standard_id, code, _standard_name in standards],
                "completion_percentage": await self._project_completion_percentage(project.id),
            }
        )

    @staticmethod
    def _coerce_assignment_status(assignment: MetricAssignment, matching_points: list[DataPoint]) -> str:
        if assignment_completed(assignment, matching_points):
            return "completed"
        if matching_points:
            return "in_progress"
        if assignment.deadline and assignment.deadline < date.today():
            return "overdue"
        return assignment.status

    @staticmethod
    def _validate_assignment_role_conflicts(
        collector_id: int | None,
        reviewer_id: int | None,
        backup_collector_id: int | None,
    ) -> None:
        distinct_user_ids = [user_id for user_id in (collector_id, reviewer_id, backup_collector_id) if user_id]
        if len(distinct_user_ids) != len(set(distinct_user_ids)):
            raise AppError(
                "ASSIGNMENT_ROLE_CONFLICT",
                409,
                "Collector, reviewer, and backup collector must be different people",
            )

    @staticmethod
    def _affected_assignment_user_ids(
        assignment: MetricAssignment,
        *,
        collector_id: int | None,
        reviewer_id: int | None,
        backup_collector_id: int | None,
    ) -> list[int]:
        return sorted(
            {
                user_id
                for user_id in (
                    assignment.collector_id,
                    assignment.reviewer_id,
                    assignment.backup_collector_id,
                    collector_id,
                    reviewer_id,
                    backup_collector_id,
                )
                if user_id
            }
        )

    async def _resolve_shared_element_id(self, payload: AssignmentCreate) -> int:
        if payload.shared_element_id:
            element_result = await self.repo.session.execute(
                select(SharedElement).where(SharedElement.id == payload.shared_element_id)
            )
            element = element_result.scalar_one_or_none()
            if not element:
                raise AppError("NOT_FOUND", 404, f"Shared element {payload.shared_element_id} not found")
            return element.id

        code = (payload.shared_element_code or "").strip()
        if not code:
            raise AppError(
                "SHARED_ELEMENT_REQUIRED",
                422,
                "Assignment requires shared_element_id or shared_element_code",
            )

        element_result = await self.repo.session.execute(
            select(SharedElement).where(SharedElement.code == code)
        )
        element = element_result.scalar_one_or_none()
        if element:
            return element.id

        name = (payload.shared_element_name or "").strip()
        if not name:
            raise AppError(
                "SHARED_ELEMENT_NAME_REQUIRED",
                422,
                "shared_element_name is required when creating a new shared element by code",
            )

        element = SharedElement(code=code, name=name)
        self.repo.session.add(element)
        await self.repo.session.flush()
        return element.id

    async def _validate_entity_in_org(self, entity_id: int | None, org_id: int | None, label: str) -> None:
        if entity_id is None:
            return
        entity_result = await self.repo.session.execute(
            select(CompanyEntity).where(CompanyEntity.id == entity_id)
        )
        entity = entity_result.scalar_one_or_none()
        if not entity:
            raise AppError("NOT_FOUND", 404, f"{label} {entity_id} not found")
        if org_id is not None and entity.organization_id != org_id:
            raise AppError("FORBIDDEN", 403, f"{label} {entity_id} does not belong to this organization")

    async def _validate_assignment_scope_in_boundary(
        self,
        project: ReportingProject,
        *,
        entity_id: int | None,
        facility_id: int | None,
    ) -> None:
        scope_entity_id = facility_id or entity_id
        if not project.boundary_definition_id or scope_entity_id is None:
            return

        membership_result = await self.repo.session.execute(
            select(BoundaryMembership).where(
                BoundaryMembership.boundary_definition_id == project.boundary_definition_id,
                BoundaryMembership.entity_id == scope_entity_id,
                BoundaryMembership.included == True,
            )
        )
        if not membership_result.scalar_one_or_none():
            raise AppError(
                "ASSIGNMENT_ENTITY_MISMATCH",
                422,
                "Assignment scope entity is outside the project's active boundary",
            )

    async def _validate_assignment_user(
        self,
        user_id: int | None,
        org_id: int,
        field_name: str,
    ) -> None:
        if user_id is None:
            return

        binding_result = await self.repo.session.execute(
            select(RoleBinding).where(
                RoleBinding.user_id == user_id,
                RoleBinding.scope_type == "organization",
                RoleBinding.scope_id == org_id,
            )
        )
        binding = binding_result.scalar_one_or_none()
        if not binding:
            raise AppError("NOT_FOUND", 404, f"User {user_id} does not belong to this organization")

        allowed_roles = {
            "collector_id": {"collector", "esg_manager", "admin"},
            "reviewer_id": {"reviewer", "esg_manager", "admin"},
            "backup_collector_id": {"collector", "esg_manager", "admin"},
        }
        if field_name in allowed_roles and binding.role not in allowed_roles[field_name]:
            readable = {
                "collector_id": "collector",
                "reviewer_id": "reviewer",
                "backup_collector_id": "backup collector",
            }[field_name]
            raise AppError(
                "INVALID_ASSIGNMENT_ROLE",
                422,
                f"User {user_id} does not have a compatible {readable} role",
            )

    async def _build_assignment_matrix(
        self,
        project_id: int,
        project_org_id: int,
        project_boundary_id: int | None,
        items: list[MetricAssignment],
        ctx: RequestContext,
    ) -> AssignmentMatrixOut:
        shared_element_ids = sorted({assignment.shared_element_id for assignment in items})
        referenced_entity_ids = sorted(
            {
                entity_id
                for assignment in items
                for entity_id in (assignment.entity_id, assignment.facility_id)
                if entity_id is not None
            }
        )
        referenced_user_ids = sorted(
            {
                user_id
                for assignment in items
                for user_id in (
                    assignment.collector_id,
                    assignment.reviewer_id,
                    assignment.backup_collector_id,
                )
                if user_id is not None
            }
        )

        shared_elements = {}
        if shared_element_ids:
            shared_result = await self.repo.session.execute(
                select(SharedElement).where(SharedElement.id.in_(shared_element_ids))
            )
            shared_elements = {element.id: element for element in shared_result.scalars().all()}

        if ctx.role in ("admin", "esg_manager", "platform_admin"):
            entities_result = await self.repo.session.execute(
                select(CompanyEntity)
                .where(CompanyEntity.organization_id == project_org_id)
                .order_by(CompanyEntity.id)
            )
        elif referenced_entity_ids:
            entities_result = await self.repo.session.execute(
                select(CompanyEntity)
                .where(CompanyEntity.id.in_(referenced_entity_ids))
                .order_by(CompanyEntity.id)
            )
        else:
            entities_result = None
        entities = list(entities_result.scalars().all()) if entities_result is not None else []
        entities_by_id = {entity.id: entity for entity in entities}

        if ctx.role in ("admin", "esg_manager", "platform_admin"):
            users_result = await self.repo.session.execute(
                select(User, RoleBinding)
                .join(RoleBinding, RoleBinding.user_id == User.id)
                .where(
                    RoleBinding.scope_type == "organization",
                    RoleBinding.scope_id == project_org_id,
                )
                .order_by(User.id)
            )
            org_users = []
            seen_user_ids = set()
            for user, binding in users_result.all():
                if user.id in seen_user_ids:
                    continue
                seen_user_ids.add(user.id)
                org_users.append((user, binding))
        elif referenced_user_ids:
            users_result = await self.repo.session.execute(
                select(User).where(User.id.in_(referenced_user_ids)).order_by(User.id)
            )
            org_users = [(user, None) for user in users_result.scalars().all()]
        else:
            org_users = []
        users_by_id = {user.id: user for user, _binding in org_users}

        memberships = {}
        if project_boundary_id and referenced_entity_ids:
            membership_result = await self.repo.session.execute(
                select(BoundaryMembership).where(
                    BoundaryMembership.boundary_definition_id == project_boundary_id,
                    BoundaryMembership.entity_id.in_(referenced_entity_ids),
                )
            )
            memberships = {membership.entity_id: membership for membership in membership_result.scalars().all()}

        data_points_result = await self.repo.session.execute(
            select(DataPoint).where(DataPoint.reporting_project_id == project_id)
        )
        project_data_points = list(data_points_result.scalars().all())

        assignments = []
        for assignment in items:
            matching_points = [
                point
                for point in project_data_points
                if assignment_matches_data_point(assignment, point)
            ]
            scope_entity_id = assignment.facility_id or assignment.entity_id
            membership = memberships.get(scope_entity_id) if scope_entity_id is not None else None
            shared_element = shared_elements.get(assignment.shared_element_id)
            entity = entities_by_id.get(assignment.entity_id) if assignment.entity_id is not None else None
            facility = entities_by_id.get(assignment.facility_id) if assignment.facility_id is not None else None
            collector = users_by_id.get(assignment.collector_id) if assignment.collector_id is not None else None
            reviewer = users_by_id.get(assignment.reviewer_id) if assignment.reviewer_id is not None else None
            backup_collector = (
                users_by_id.get(assignment.backup_collector_id)
                if assignment.backup_collector_id is not None
                else None
            )
            sla_state = resolve_assignment_sla(
                deadline=assignment.deadline,
                escalation_after_days=assignment.escalation_after_days,
                completed=assignment_completed(assignment, matching_points),
            )

            assignments.append(
                AssignmentMatrixRowOut(
                    id=assignment.id,
                    shared_element_id=assignment.shared_element_id,
                    shared_element_code=shared_element.code if shared_element else str(assignment.shared_element_id),
                    shared_element_name=shared_element.name if shared_element else f"Shared element {assignment.shared_element_id}",
                    entity_id=assignment.entity_id,
                    entity_name=entity.name if entity else None,
                    facility_id=assignment.facility_id,
                    facility_name=facility.name if facility else None,
                    boundary_included=membership.included if membership else False,
                    consolidation_method=membership.consolidation_method or "full" if membership else "full",
                    collector_id=assignment.collector_id,
                    collector_name=collector.full_name if collector else None,
                    reviewer_id=assignment.reviewer_id,
                    reviewer_name=reviewer.full_name if reviewer else None,
                    backup_collector_id=assignment.backup_collector_id,
                    backup_collector_name=backup_collector.full_name if backup_collector else None,
                    deadline=assignment.deadline,
                    escalation_after_days=sla_state.escalation_after_days,
                    sla_status=sla_state.status,
                    days_overdue=sla_state.days_overdue,
                    days_until_deadline=sla_state.days_until_deadline,
                    status=self._coerce_assignment_status(assignment, matching_points),
                    created_at=assignment.created_at.isoformat() if assignment.created_at else None,
                )
            )

        matrix_users = [
            AssignmentMatrixUserOut(id=user.id, name=user.full_name, email=user.email)
            for user, _binding in org_users
        ]
        matrix_entities = [
            AssignmentMatrixEntityOut(id=entity.id, name=entity.name, code=entity.code)
            for entity in entities
        ]
        return AssignmentMatrixOut(
            assignments=assignments,
            users=matrix_users,
            entities=matrix_entities,
        )

    async def _apply_assignment_update(
        self,
        assignment: MetricAssignment,
        field: str,
        value: str,
        ctx: RequestContext,
        org_id: int,
    ) -> MetricAssignment:
        if field not in {"collector_id", "reviewer_id", "backup_collector_id", "deadline", "escalation_after_days"}:
            raise AppError(
                "INVALID_ASSIGNMENT_FIELD",
                422,
                f"Unsupported assignment update field '{field}'",
            )

        if field in {"collector_id", "reviewer_id", "backup_collector_id"}:
            parsed_value = int(value) if value else None
            await self._validate_assignment_user(parsed_value, org_id, field)
        elif field == "escalation_after_days":
            parsed_value = int(value) if value else 3
            if parsed_value < 1:
                raise AppError("INVALID_ESCALATION_WINDOW", 422, "escalation_after_days must be at least 1")
        else:
            parsed_value = date.fromisoformat(value) if value else None

        next_collector_id = parsed_value if field == "collector_id" else assignment.collector_id
        next_reviewer_id = parsed_value if field == "reviewer_id" else assignment.reviewer_id
        next_backup_collector_id = (
            parsed_value if field == "backup_collector_id" else assignment.backup_collector_id
        )
        self._validate_assignment_role_conflicts(
            next_collector_id,
            next_reviewer_id,
            next_backup_collector_id,
        )

        updated = await self.repo.update_assignment(assignment.id, **{field: parsed_value})
        await self._audit(
            "MetricAssignment",
            "assignment_updated",
            ctx,
            entity_id=assignment.id,
            changes={field: value or None},
        )
        await get_event_bus().publish(
            AssignmentUpdated(
                assignment_id=assignment.id,
                project_id=assignment.reporting_project_id,
                organization_id=org_id,
                affected_user_ids=self._affected_assignment_user_ids(
                    assignment,
                    collector_id=next_collector_id,
                    reviewer_id=next_reviewer_id,
                    backup_collector_id=next_backup_collector_id,
                ),
                changes={field: parsed_value},
                updated_by=ctx.user_id,
            )
        )
        return updated

    async def _build_project_gate_context(
        self, project_id: int, ctx: RequestContext, completion_threshold: int
    ) -> dict:
        project = await get_project_for_ctx(
            self.repo.session,
            project_id,
            ctx,
            allow_collectors=False,
            allow_reviewers=False,
        )

        standard_count = (
            await self.repo.session.execute(
                select(func.count()).select_from(ReportingProjectStandard).where(
                    ReportingProjectStandard.reporting_project_id == project_id
                )
            )
        ).scalar_one()
        total_data_point_count = (
            await self.repo.session.execute(
                select(func.count()).select_from(DataPoint).where(
                    DataPoint.reporting_project_id == project_id
                )
            )
        ).scalar_one()
        reviewed_count = (
            await self.repo.session.execute(
                select(func.count()).select_from(DataPoint).where(
                    DataPoint.reporting_project_id == project_id,
                    DataPoint.status.in_(("approved", "rejected", "needs_revision")),
                )
            )
        ).scalar_one()
        unresolved_review_count = (
            await self.repo.session.execute(
                select(func.count()).select_from(DataPoint).where(
                    DataPoint.reporting_project_id == project_id,
                    DataPoint.status.in_(("rejected", "needs_revision", "in_review")),
                )
            )
        ).scalar_one()
        approved_count = (
            await self.repo.session.execute(
                select(func.count()).select_from(DataPoint).where(
                    DataPoint.reporting_project_id == project_id,
                    DataPoint.status == "approved",
                )
            )
        ).scalar_one()

        status_rows = (
            await self.repo.session.execute(
                select(RequirementItemStatus.status, func.count())
                .where(RequirementItemStatus.reporting_project_id == project_id)
                .group_by(RequirementItemStatus.status)
            )
        ).all()
        status_counts = {status: count for status, count in status_rows}
        total_item_statuses = sum(status_counts.values())
        complete_items = status_counts.get("complete", 0)
        snapshot = (
            await self.repo.session.execute(
                select(BoundarySnapshot).where(BoundarySnapshot.reporting_project_id == project_id)
            )
        ).scalar_one_or_none()
        if total_item_statuses:
            completion_percent = (complete_items / total_item_statuses) * 100
        elif total_data_point_count:
            completion_percent = (approved_count / total_data_point_count) * 100
        else:
            completion_percent = 0

        return {
            "project": project,
            "standard_count": standard_count,
            "reviewed_count": reviewed_count,
            "total_data_point_count": total_data_point_count,
            "unresolved_review_count": unresolved_review_count,
            "completion_percent": round(completion_percent, 1),
            "completion_threshold": completion_threshold,
            "boundary_snapshot_locked": (
                snapshot is not None
                and snapshot.boundary_definition_id == project.boundary_definition_id
            ),
        }

    async def _check_project_gates(
        self, action: str, context: dict, ctx: RequestContext
    ) -> dict:
        result = await self.project_gate_engine.check(action, context)
        if not result.allowed:
            failed = [
                {"code": gate.code, "type": gate.gate_type, "message": gate.message, "severity": gate.severity}
                for gate in result.failed_gates
            ]
            warnings = [
                {"code": gate.code, "type": gate.gate_type, "message": gate.message}
                for gate in result.warnings
            ]
            primary = result.failed_gates[0]
            raise GateBlockedError(
                code=primary.code,
                message=primary.message,
                failed_gates=failed,
                warnings=warnings,
            )
        return {
            "warnings": [
                {"code": gate.code, "type": gate.gate_type, "message": gate.message}
                for gate in result.warnings
            ]
        }

    # --- Projects ---
    async def create_project(self, payload: ProjectCreate, ctx: RequestContext) -> ProjectOut:
        self._require_manager(ctx)
        if not ctx.organization_id:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required")
        p = await self.repo.create_project(ctx.organization_id, **payload.model_dump())
        return await self._build_project_out(p)

    async def list_projects(self, ctx: RequestContext, page: int = 1, page_size: int = 20) -> ProjectListOut:
        if not ctx.organization_id:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required")
        items, total = await self.repo.list_projects(ctx.organization_id, page, page_size)
        if ctx.role == "collector":
            items = [
                project
                for project in items
                if await user_has_project_assignment(self.repo.session, project.id, ctx.user_id, "collector")
            ]
            total = len(items)
        elif ctx.role == "reviewer":
            items = [
                project
                for project in items
                if await user_has_project_assignment(self.repo.session, project.id, ctx.user_id, "reviewer")
            ]
            total = len(items)
        return ProjectListOut(
            items=[await self._build_project_out(p) for p in items],
            total=total,
        )

    async def get_project(self, project_id: int, ctx: RequestContext) -> ProjectOut:
        self._require_manager(ctx)
        p = await get_project_for_ctx(
            self.repo.session, project_id, ctx, allow_collectors=False, allow_reviewers=False
        )
        return await self._build_project_out(p)

    async def add_standard(self, project_id: int, payload: ProjectStandardAdd, ctx: RequestContext):
        self._require_manager(ctx)
        await get_project_for_ctx(self.repo.session, project_id, ctx)
        await self.repo.add_standard(project_id, payload.standard_id, payload.is_base_standard)
        await self._audit(
            "ReportingProject",
            "project_standard_added",
            ctx,
            entity_id=project_id,
            changes=payload.model_dump(),
        )
        return {"project_id": project_id, "standard_id": payload.standard_id}

    async def list_project_standards(
        self, project_id: int, ctx: RequestContext
    ) -> ProjectStandardSummaryListOut:
        self._require_manager(ctx)
        await get_project_for_ctx(
            self.repo.session, project_id, ctx, allow_collectors=False, allow_reviewers=False
        )

        standards = await self.completeness_repo.list_project_standards(project_id)
        disclosure_counts = {
            standard_id: disclosure_count
            for standard_id, disclosure_count in (
                await self.repo.session.execute(
                    select(
                        DisclosureRequirement.standard_id,
                        func.count(DisclosureRequirement.id),
                    )
                    .join(
                        ReportingProjectStandard,
                        ReportingProjectStandard.standard_id == DisclosureRequirement.standard_id,
                    )
                    .where(ReportingProjectStandard.reporting_project_id == project_id)
                    .group_by(DisclosureRequirement.standard_id)
                )
            ).all()
        }

        items: list[ProjectStandardSummaryOut] = []
        for standard_id, code, name in standards:
            items_with_disclosures = await self.completeness_repo.list_project_items(project_id, standard_id)
            item_ids = [item.id for item, _disclosure in items_with_disclosures]
            statuses = await self.completeness_repo.list_project_item_statuses(project_id, item_ids)
            status_by_item = {status.requirement_item_id: status.status for status in statuses}

            complete = partial = missing = 0
            for item_id in item_ids:
                status = status_by_item.get(item_id, "missing")
                if status == "not_applicable":
                    continue
                if status == "complete":
                    complete += 1
                elif status == "partial":
                    partial += 1
                else:
                    missing += 1
            total = complete + partial + missing
            items.append(
                ProjectStandardSummaryOut(
                    id=standard_id,
                    standard_id=standard_id,
                    standard_name=name,
                    code=code,
                    disclosure_count=disclosure_counts.get(standard_id, 0),
                    completion_percentage=round((complete / total) * 100, 1) if total else 0.0,
                )
            )

        return ProjectStandardSummaryListOut(items=items)

    async def get_assignment_summary(
        self, project_id: int, ctx: RequestContext
    ) -> ProjectAssignmentSummaryListOut:
        self._require_manager(ctx)
        await get_project_for_ctx(
            self.repo.session, project_id, ctx, allow_collectors=False, allow_reviewers=False
        )
        assignments = await self.repo.list_assignments(project_id)
        data_points = list(
            (
                await self.repo.session.execute(
                    select(DataPoint).where(DataPoint.reporting_project_id == project_id)
                )
            ).scalars().all()
        )

        user_ids = sorted(
            {
                user_id
                for assignment in assignments
                for user_id in (
                    assignment.collector_id,
                    assignment.reviewer_id,
                    assignment.backup_collector_id,
                )
                if user_id is not None
            }
        )
        users = {}
        if user_ids:
            users = {
                user.id: user
                for user in (
                    await self.repo.session.execute(select(User).where(User.id.in_(user_ids)))
                ).scalars().all()
            }

        summary_by_user: dict[tuple[int, str], ProjectAssignmentSummaryOut] = {}
        for assignment in assignments:
            matching_points = [
                point for point in data_points if assignment_matches_data_point(assignment, point)
            ]
            completed = assignment_completed(assignment, matching_points)
            for role, user_id in (
                ("collector", assignment.collector_id),
                ("reviewer", assignment.reviewer_id),
                ("backup_collector", assignment.backup_collector_id),
            ):
                if user_id is None:
                    continue
                user = users.get(user_id)
                bucket = summary_by_user.setdefault(
                    (user_id, role),
                    ProjectAssignmentSummaryOut(
                        id=user_id,
                        user_name=user.full_name if user else f"User {user_id}",
                        email=user.email if user else "",
                        role=role,
                        assigned_disclosures=0,
                        completed=0,
                    ),
                )
                bucket.assigned_disclosures += 1
                if completed:
                    bucket.completed += 1

        items = sorted(summary_by_user.values(), key=lambda item: (item.role, item.user_name.lower()))
        return ProjectAssignmentSummaryListOut(items=items)

    # --- Assignments ---
    async def create_assignment(
        self, project_id: int, payload: AssignmentCreate, ctx: RequestContext
    ) -> AssignmentOut:
        self._require_manager(ctx)

        self._validate_assignment_role_conflicts(
            payload.collector_id,
            payload.reviewer_id,
            payload.backup_collector_id,
        )

        project = await get_project_for_ctx(self.repo.session, project_id, ctx)
        await self._validate_entity_in_org(payload.entity_id, project.organization_id, "Entity")
        await self._validate_entity_in_org(payload.facility_id, project.organization_id, "Facility")
        await self._validate_assignment_scope_in_boundary(
            project,
            entity_id=payload.entity_id,
            facility_id=payload.facility_id,
        )
        await self._validate_assignment_user(payload.collector_id, project.organization_id, "collector_id")
        await self._validate_assignment_user(payload.reviewer_id, project.organization_id, "reviewer_id")
        await self._validate_assignment_user(
            payload.backup_collector_id,
            project.organization_id,
            "backup_collector_id",
        )
        shared_element_id = await self._resolve_shared_element_id(payload)

        assignment_payload = {
            "shared_element_id": shared_element_id,
            "entity_id": payload.entity_id,
            "facility_id": payload.facility_id,
            "collector_id": payload.collector_id,
            "reviewer_id": payload.reviewer_id,
            "backup_collector_id": payload.backup_collector_id,
            "deadline": payload.deadline,
            "escalation_after_days": payload.escalation_after_days,
        }
        a = await self.repo.create_assignment(project_id, **assignment_payload)
        assignment_changes = {
            **payload.model_dump(mode="json"),
            "shared_element_id": shared_element_id,
        }
        await self._audit("MetricAssignment", "assignment_created", ctx, entity_id=a.id,
                          changes=assignment_changes)
        await get_event_bus().publish(
            AssignmentCreated(
                assignment_id=a.id,
                project_id=project_id,
                organization_id=project.organization_id,
                collector_id=payload.collector_id,
                reviewer_id=payload.reviewer_id,
                shared_element_id=shared_element_id,
                assigned_by=ctx.user_id,
            )
        )
        return AssignmentOut.model_validate(a)

    async def list_assignments(self, project_id: int, ctx: RequestContext) -> AssignmentMatrixOut:
        if ctx.role == "collector":
            project = await get_project_for_ctx(
                self.repo.session,
                project_id,
                ctx,
                allow_collectors=True,
                allow_reviewers=False,
            )
            items = await get_user_assignments(
                self.repo.session,
                project_id,
                ctx.user_id,
                "collector",
            )
        else:
            self._require_manager(ctx)
            project = await get_project_for_ctx(
                self.repo.session,
                project_id,
                ctx,
                allow_collectors=False,
                allow_reviewers=False,
            )
            items = await self.repo.list_assignments(project_id)
        return await self._build_assignment_matrix(
            project_id=project_id,
            project_org_id=project.organization_id,
            project_boundary_id=project.boundary_definition_id,
            items=items,
            ctx=ctx,
        )

    async def inline_update_assignment(
        self,
        project_id: int,
        payload: AssignmentInlineUpdate,
        ctx: RequestContext,
    ) -> AssignmentMatrixRowOut:
        self._require_manager(ctx)
        project = await get_project_for_ctx(
            self.repo.session, project_id, ctx, allow_collectors=False, allow_reviewers=False
        )
        assignment = await self.repo.get_assignment_or_raise(payload.id)
        if assignment.reporting_project_id != project_id:
            raise AppError("NOT_FOUND", 404, f"Assignment {payload.id} not found in project {project_id}")

        updated = await self._apply_assignment_update(
            assignment=assignment,
            field=payload.field,
            value=payload.value,
            ctx=ctx,
            org_id=project.organization_id,
        )
        matrix = await self._build_assignment_matrix(
            project_id=project_id,
            project_org_id=project.organization_id,
            project_boundary_id=project.boundary_definition_id,
            items=[updated],
            ctx=ctx,
        )
        return matrix.assignments[0]

    async def bulk_update_assignments(
        self,
        project_id: int,
        payload: AssignmentBulkUpdate,
        ctx: RequestContext,
    ) -> dict:
        self._require_manager(ctx)
        if not payload.ids:
            raise AppError("ASSIGNMENT_IDS_REQUIRED", 422, "Bulk update requires at least one assignment id")

        project = await get_project_for_ctx(
            self.repo.session, project_id, ctx, allow_collectors=False, allow_reviewers=False
        )
        updated_ids: list[int] = []
        for assignment_id in payload.ids:
            assignment = await self.repo.get_assignment_or_raise(assignment_id)
            if assignment.reporting_project_id != project_id:
                raise AppError(
                    "NOT_FOUND",
                    404,
                    f"Assignment {assignment_id} not found in project {project_id}",
                )
            updated = await self._apply_assignment_update(
                assignment=assignment,
                field=payload.field,
                value=payload.value,
                ctx=ctx,
                org_id=project.organization_id,
            )
            updated_ids.append(updated.id)
        return {"updated_count": len(updated_ids), "assignment_ids": updated_ids}

    # --- Boundaries ---
    async def create_boundary(self, payload: BoundaryDefCreate, ctx: RequestContext) -> BoundaryDefOut:
        if ctx.role not in ("admin", "platform_admin"):
            raise AppError("FORBIDDEN", 403, "Only admin can create boundaries")
        if not ctx.organization_id:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required")
        b = await self.repo.create_boundary(ctx.organization_id, **payload.model_dump())
        await self._audit("BoundaryDefinition", "create_boundary", ctx, entity_id=b.id,
                          changes=payload.model_dump())
        return BoundaryDefOut.model_validate({**BoundaryDefOut.model_validate(b).model_dump(), "entity_count": 0})

    async def list_boundaries(self, ctx: RequestContext) -> list[BoundaryDefOut]:
        if not ctx.organization_id:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required")
        items = await self.repo.list_boundaries(ctx.organization_id)
        boundary_ids = [boundary.id for boundary in items]
        entity_counts = {}
        if boundary_ids:
            entity_counts = {
                boundary_id: entity_count
                for boundary_id, entity_count in (
                    await self.repo.session.execute(
                        select(
                            BoundaryMembership.boundary_definition_id,
                            func.count(BoundaryMembership.id),
                        )
                        .where(
                            BoundaryMembership.boundary_definition_id.in_(boundary_ids),
                            BoundaryMembership.included == True,
                        )
                        .group_by(BoundaryMembership.boundary_definition_id)
                    )
                ).all()
            }
        return [
            BoundaryDefOut.model_validate(
                {
                    **BoundaryDefOut.model_validate(boundary).model_dump(),
                    "entity_count": entity_counts.get(boundary.id, 0),
                }
            )
            for boundary in items
        ]

    async def apply_boundary(self, project_id: int, boundary_id: int, ctx: RequestContext) -> ProjectOut:
        self._require_manager(ctx)
        p = await get_project_for_ctx(self.repo.session, project_id, ctx, allow_collectors=False, allow_reviewers=False)
        boundary = await self.repo.get_boundary_or_raise(boundary_id)
        AuthPolicy.check_tenant_isolation(ctx, boundary.organization_id)
        if p.status == "published":
            raise AppError("PROJECT_LOCKED", 422, "Cannot change boundary for published project")
        p = await self.repo.update_project(project_id, boundary_definition_id=boundary_id)
        await self.repo.session.execute(
            delete(BoundarySnapshot).where(BoundarySnapshot.reporting_project_id == project_id)
        )
        await self._audit("ReportingProject", "apply_boundary_to_project", ctx, entity_id=project_id,
                          changes={"boundary_id": boundary_id})
        await get_event_bus().publish(
            BoundaryAppliedToProject(
                project_id=project_id,
                boundary_id=boundary_id,
                organization_id=p.organization_id,
                applied_by=ctx.user_id,
            )
        )
        return ProjectOut.model_validate(p)

    async def start_project(self, project_id: int, ctx: RequestContext) -> dict:
        self._require_manager(ctx)
        project = await get_project_for_ctx(
            self.repo.session, project_id, ctx, allow_collectors=False, allow_reviewers=False
        )
        if project.status != "draft":
            raise AppError("INVALID_WORKFLOW_TRANSITION", 422, "Project can only be started from draft")
        gate_result = await self._check_project_gates(
            "start_project",
            await self._build_project_gate_context(project_id, ctx, completion_threshold=0),
            ctx,
        )
        project = await self.repo.update_project(project_id, status="active")
        await self._audit("ReportingProject", "project_started", ctx, entity_id=project_id)
        await get_event_bus().publish(
            ProjectStarted(
                project_id=project.id,
                organization_id=project.organization_id,
                started_by=ctx.user_id,
                project_name=project.name,
            )
        )
        return {"id": project.id, "status": project.status, **gate_result}

    async def review_project(self, project_id: int, ctx: RequestContext) -> dict:
        self._require_manager(ctx)
        project = await get_project_for_ctx(
            self.repo.session, project_id, ctx, allow_collectors=False, allow_reviewers=False
        )
        if project.status != "active":
            raise AppError("INVALID_WORKFLOW_TRANSITION", 422, "Project can only move to review from active")
        gate_result = await self._check_project_gates(
            "review_project",
            await self._build_project_gate_context(project_id, ctx, completion_threshold=80),
            ctx,
        )
        assignments = await self.repo.list_assignments(project_id)
        project = await self.repo.update_project(project_id, status="review")
        await self._audit("ReportingProject", "project_review_started", ctx, entity_id=project_id)
        await get_event_bus().publish(
            ProjectReviewStarted(
                project_id=project.id,
                organization_id=project.organization_id,
                started_by=ctx.user_id,
                project_name=project.name,
                target_user_ids=sorted({a.reviewer_id for a in assignments if a.reviewer_id}),
            )
        )
        return {"id": project.id, "status": project.status, **gate_result}

    async def publish_project(self, project_id: int, ctx: RequestContext) -> dict:
        self._require_manager(ctx)
        project = await get_project_for_ctx(
            self.repo.session, project_id, ctx, allow_collectors=False, allow_reviewers=False
        )
        if project.status == "published":
            raise AppError("CONFLICT", 409, "Project already published")
        if project.status != "review":
            raise AppError("INVALID_WORKFLOW_TRANSITION", 422, "Project can only be published from review")
        gate_result = await self._check_project_gates(
            "publish_project",
            await self._build_project_gate_context(project_id, ctx, completion_threshold=100),
            ctx,
        )
        project = await self.repo.update_project(project_id, status="published")
        await self._audit("ReportingProject", "project_published", ctx, entity_id=project_id)
        await get_event_bus().publish(
            ProjectPublished(
                project_id=project.id,
                organization_id=project.organization_id,
                published_by=ctx.user_id,
                project_name=project.name,
            )
        )
        return {"project_id": project.id, "status": project.status, **gate_result}

    async def rollback_project(self, project_id: int, comment: str | None, ctx: RequestContext) -> dict:
        self._require_manager(ctx)
        project = await get_project_for_ctx(
            self.repo.session, project_id, ctx, allow_collectors=False, allow_reviewers=False
        )
        if project.status != "published":
            raise AppError("INVALID_WORKFLOW_TRANSITION", 422, "Only published projects can be rolled back")
        if not comment:
            raise AppError("ROLLBACK_COMMENT_REQUIRED", 422, "Rollback comment is required")
        project = await self.repo.update_project(project_id, status="active")
        await self._audit(
            "ReportingProject",
            "project_rolled_back",
            ctx,
            entity_id=project_id,
            changes={"comment": comment},
        )
        return {"project_id": project.id, "status": project.status}
