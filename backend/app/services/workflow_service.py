import logging
from types import SimpleNamespace

from sqlalchemy import select

from app.core.access import assignment_matches_data_point, get_data_point_for_ctx
from app.core.dashboard_cache import invalidate_dashboard_project
from app.core.dependencies import RequestContext
from app.core.exceptions import AppError, GateBlockedError
from app.db.models.completeness import RequirementItemDataPoint, RequirementItemStatus
from app.db.models.project import MetricAssignment
from app.db.models.requirement_item import RequirementItem
from app.events.bus import (
    DataPointApproved,
    DataPointRejected,
    DataPointRevisionRequested,
    DataPointRolledBack,
    DataPointSubmitted,
    get_event_bus,
)
from app.repositories.audit_repo import AuditRepository
from app.services.data_point_service import create_data_point_version
from app.repositories.completeness_repo import CompletenessRepository
from app.repositories.data_point_repo import DataPointRepository
from app.repositories.evidence_repo import EvidenceRepository
from app.services.completeness_service import CompletenessService
from app.workflows.gates.base import GateEngine
from app.workflows.gates.boundary_gate import (
    BoundaryInclusionGate,
    BoundaryNotDefinedGate,
    BoundaryNotLockedGate,
)
from app.workflows.gates.completeness_gate import ProjectIncompleteGate, RequirementIncompleteGate
from app.workflows.gates.data_gate import DataValidationGate, InvalidValueTypeGate, MissingDataGate
from app.workflows.gates.evidence_gate import EvidenceRequiredGate
from app.workflows.gates.review_gate import (
    NoAssignmentsGate,
    NoRequirementsGate,
    NoReviewerAssignedGate,
    ProjectLockedGate,
    UnresolvedReviewGate,
    UnsubmittedDataGate,
)
from app.workflows.gates.workflow_gate import (
    CommentRequiredGate,
    DataPointLockedGate,
    WorkflowTransitionGate,
)

logger = logging.getLogger(__name__)


class WorkflowService:
    def __init__(
        self,
        dp_repo: DataPointRepository,
        evidence_repo: EvidenceRepository | None = None,
        audit_repo: AuditRepository | None = None,
    ):
        self.dp_repo = dp_repo
        self.audit_repo = audit_repo
        self.gate_engine = GateEngine([
            # Workflow gates
            WorkflowTransitionGate(),
            CommentRequiredGate(),
            DataPointLockedGate(),
            ProjectLockedGate(),
            # Data gates
            DataValidationGate(),
            InvalidValueTypeGate(),
            MissingDataGate(),
            # Evidence gates
            EvidenceRequiredGate(evidence_repo),
            # Boundary gates
            BoundaryInclusionGate(),
            BoundaryNotDefinedGate(),
            BoundaryNotLockedGate(),
            # Completeness gates
            RequirementIncompleteGate(),
            ProjectIncompleteGate(),
            # Review gates
            UnresolvedReviewGate(),
            NoRequirementsGate(),
            NoReviewerAssignedGate(),
        ])

    async def _refresh_bound_item_statuses(self, project_id: int, dp_id: int) -> None:
        binding_result = await self.dp_repo.session.execute(
            select(RequirementItemDataPoint.requirement_item_id).where(
                RequirementItemDataPoint.reporting_project_id == project_id,
                RequirementItemDataPoint.data_point_id == dp_id,
            )
        )
        item_ids = sorted({item_id for item_id in binding_result.scalars().all()})
        if not item_ids:
            return

        completeness_service = CompletenessService(CompletenessRepository(self.dp_repo.session))
        for item_id in item_ids:
            await completeness_service.calculate_item_status(project_id, item_id)

    async def _check_gates(self, action: str, context: dict, ctx: RequestContext | None = None) -> dict:
        result = await self.gate_engine.check(action, context)

        # Log gate check to audit
        gate_log = {
            "action": action,
            "allowed": result.allowed,
            "failed_codes": [g.code for g in result.failed_gates],
            "warning_codes": [w.code for w in result.warnings],
        }
        logger.info("Gate check: %s", gate_log)

        if self.audit_repo and ctx:
            dp = context.get("data_point")
            await self.audit_repo.log(
                entity_type="DataPoint",
                entity_id=dp.id if dp else None,
                action="gate_check",
                user_id=ctx.user_id,
                organization_id=ctx.organization_id,
                changes=gate_log,
                performed_by_platform_admin=ctx.is_platform_admin,
            )

        if not result.allowed:
            failed = [
                {"code": g.code, "type": g.gate_type, "message": g.message, "severity": g.severity}
                for g in result.failed_gates
            ]
            warnings = [
                {"code": w.code, "type": w.gate_type, "message": w.message}
                for w in result.warnings
            ]
            # Use first gate's code for backward compatibility
            primary_code = result.failed_gates[0].code if result.failed_gates else "GATE_BLOCKED"
            primary_message = result.failed_gates[0].message if result.failed_gates else "Action blocked by gate checks"
            raise GateBlockedError(
                code=primary_code,
                message=primary_message,
                failed_gates=failed,
                warnings=warnings,
            )

        return {
            "warnings": [
                {"code": w.code, "type": w.gate_type, "message": w.message}
                for w in result.warnings
            ]
        }

    async def _audit(self, action: str, entity_id: int, ctx: RequestContext, changes: dict | None = None):
        if self.audit_repo:
            await self.audit_repo.log(
                entity_type="DataPoint",
                entity_id=entity_id,
                action=action,
                user_id=ctx.user_id,
                organization_id=ctx.organization_id,
                changes=changes,
                performed_by_platform_admin=ctx.is_platform_admin,
            )

    def _require_submit_access(self, ctx: RequestContext) -> None:
        if ctx.role not in ("collector", "admin", "esg_manager", "platform_admin"):
            raise AppError("FORBIDDEN", 403, "Only collectors or managers can submit data points")

    def _require_review_access(self, ctx: RequestContext) -> None:
        if ctx.role not in ("reviewer", "admin", "esg_manager", "platform_admin"):
            raise AppError("FORBIDDEN", 403, "Only reviewers or managers can review data points")

    def _require_rollback_access(self, ctx: RequestContext) -> None:
        if ctx.role not in ("admin", "esg_manager", "platform_admin"):
            raise AppError("FORBIDDEN", 403, "Only admin or ESG manager can rollback approved data points")

    async def _get_matching_reviewer_assignments(self, dp) -> list[MetricAssignment]:
        assignment_result = await self.dp_repo.session.execute(
            select(MetricAssignment).where(
                MetricAssignment.reporting_project_id == dp.reporting_project_id,
                MetricAssignment.shared_element_id == dp.shared_element_id,
                MetricAssignment.reviewer_id.is_not(None),
            )
        )
        return [
            assignment
            for assignment in assignment_result.scalars().all()
            if assignment_matches_data_point(assignment, dp)
        ]

    async def _build_gate_context(
        self,
        dp,
        project,
        ctx: RequestContext,
        target_status: str,
        comment: str | None = None,
    ) -> dict:
        binding_result = await self.dp_repo.session.execute(
            select(RequirementItemDataPoint).where(
                RequirementItemDataPoint.reporting_project_id == dp.reporting_project_id,
                RequirementItemDataPoint.data_point_id == dp.id,
            )
        )
        bindings = list(binding_result.scalars().all())
        item_ids = [binding.requirement_item_id for binding in bindings]

        requirement_items = []
        item_statuses: list[str] = []

        if item_ids:
            items_result = await self.dp_repo.session.execute(
                select(RequirementItem).where(RequirementItem.id.in_(item_ids))
            )
            item_map = {item.id: item for item in items_result.scalars().all()}

            status_result = await self.dp_repo.session.execute(
                select(RequirementItemStatus).where(
                    RequirementItemStatus.reporting_project_id == dp.reporting_project_id,
                    RequirementItemStatus.requirement_item_id.in_(item_ids),
                )
            )
            status_map = {
                item_status.requirement_item_id: item_status.status
                for item_status in status_result.scalars().all()
            }

            requirement_items = [item_map[item_id] for item_id in item_ids if item_id in item_map]
            item_statuses = [status_map.get(item_id, "missing") for item_id in item_ids]

        # ── Resolve expected_value_type from first bound requirement item ──
        expected_value_type = None
        if requirement_items:
            expected_value_type = getattr(requirement_items[0], "value_type", None)

        # ── Check if a reviewer is assigned to this DP's scope ────────
        matching_reviewer_assignments = await self._get_matching_reviewer_assignments(dp)
        reviewer_assigned = bool(matching_reviewer_assignments)

        # ── Check boundary membership for scoped data points ───────────
        boundary_entity_included: bool | None = None
        scope_entity_id = getattr(dp, "facility_id", None) or getattr(dp, "entity_id", None)
        if (
            scope_entity_id is not None
            and getattr(project, "boundary_definition_id", None)
        ):
            from app.db.models.boundary import BoundaryMembership

            membership_result = await self.dp_repo.session.execute(
                select(BoundaryMembership).where(
                    BoundaryMembership.boundary_definition_id == project.boundary_definition_id,
                    BoundaryMembership.entity_id == scope_entity_id,
                    BoundaryMembership.included == True,  # noqa: E712
                )
            )
            boundary_entity_included = membership_result.scalar_one_or_none() is not None

        return {
            "data_point": dp,
            "project": project,
            "target_status": target_status,
            "role": ctx.role,
            "comment": comment,
            "requirement_bindings": bindings,
            "requirement_items": requirement_items,
            "requirement_item": requirement_items[0] if requirement_items else None,
            "item_statuses": item_statuses,
            "item_status": item_statuses[0] if item_statuses else None,
            # Gate-specific fields that were previously missing:
            "expected_value_type": expected_value_type,
            "reviewer_assigned": reviewer_assigned,
            "boundary_entity_included": boundary_entity_included,
        }

    @staticmethod
    def _build_preview_data_point(dp, draft: dict | None):
        if not draft:
            return dp

        preview_payload = {
            "id": dp.id,
            "reporting_project_id": dp.reporting_project_id,
            "shared_element_id": dp.shared_element_id,
            "entity_id": getattr(dp, "entity_id", None),
            "facility_id": getattr(dp, "facility_id", None),
            "status": dp.status,
            "numeric_value": dp.numeric_value,
            "text_value": dp.text_value,
            "unit_code": getattr(dp, "unit_code", None),
            "methodology_id": getattr(dp, "methodology_id", None),
        }
        preview_payload.update(draft)

        if draft.get("numeric_value") is not None and "text_value" not in draft:
            preview_payload["text_value"] = None
        if draft.get("text_value") is not None and "numeric_value" not in draft:
            preview_payload["numeric_value"] = None

        return SimpleNamespace(**preview_payload)

    async def submit(self, dp_id: int, ctx: RequestContext) -> dict:
        self._require_submit_access(ctx)
        dp, project, _ = await get_data_point_for_ctx(self.dp_repo.session, dp_id, ctx)
        context = await self._build_gate_context(dp, project, ctx, "submitted")
        gate_result = await self._check_gates("submit_data_point", context, ctx)

        dp = await self.dp_repo.update(dp_id, status="submitted")
        await create_data_point_version(
            self.dp_repo.session, dp, changed_by=ctx.user_id, change_reason="submitted"
        )
        await self._audit("data_point_submitted", dp_id, ctx)

        # Auto-transition to in_review if reviewer is assigned
        final_status = "submitted"
        matching_reviewers = await self._get_matching_reviewer_assignments(dp)
        if matching_reviewers:
            dp = await self.dp_repo.update(dp_id, status="in_review")
            await create_data_point_version(
                self.dp_repo.session, dp, changed_by=ctx.user_id, change_reason="auto_in_review"
            )
            final_status = "in_review"
        await self._refresh_bound_item_statuses(dp.reporting_project_id, dp.id)
        await get_event_bus().publish(
            DataPointSubmitted(
                data_point_id=dp.id,
                submitted_by=ctx.user_id,
                project_id=dp.reporting_project_id,
                organization_id=project.organization_id,
                target_user_ids=sorted(
                    {
                        assignment.reviewer_id
                        for assignment in matching_reviewers
                        if assignment.reviewer_id
                    }
                ),
            )
        )
        await invalidate_dashboard_project(dp.reporting_project_id)

        return {"id": dp.id, "status": final_status, **gate_result}

    async def approve(self, dp_id: int, comment: str | None, ctx: RequestContext) -> dict:
        self._require_review_access(ctx)
        dp, project, _ = await get_data_point_for_ctx(self.dp_repo.session, dp_id, ctx)
        context = await self._build_gate_context(dp, project, ctx, "approved", comment)
        gate_result = await self._check_gates("approve_data_point", context, ctx)

        dp = await self.dp_repo.update(dp_id, status="approved", review_comment=comment)
        await create_data_point_version(
            self.dp_repo.session, dp, changed_by=ctx.user_id, change_reason="approved"
        )
        await self._refresh_bound_item_statuses(dp.reporting_project_id, dp.id)
        await self._audit("data_point_approved", dp_id, ctx, {"comment": comment})
        await get_event_bus().publish(
            DataPointApproved(
                data_point_id=dp.id,
                reviewed_by=ctx.user_id,
                organization_id=project.organization_id,
                target_user_ids=[dp.created_by] if dp.created_by else [],
            )
        )
        await invalidate_dashboard_project(dp.reporting_project_id)
        return {"id": dp.id, "status": dp.status, **gate_result}

    async def reject(self, dp_id: int, comment: str | None, ctx: RequestContext) -> dict:
        self._require_review_access(ctx)
        dp, project, _ = await get_data_point_for_ctx(self.dp_repo.session, dp_id, ctx)
        context = await self._build_gate_context(dp, project, ctx, "rejected", comment)
        gate_result = await self._check_gates("reject_data_point", context, ctx)

        dp = await self.dp_repo.update(dp_id, status="rejected", review_comment=comment)
        await create_data_point_version(
            self.dp_repo.session, dp, changed_by=ctx.user_id, change_reason="rejected"
        )
        await self._refresh_bound_item_statuses(dp.reporting_project_id, dp.id)
        await self._audit("data_point_rejected", dp_id, ctx, {"comment": comment})
        await get_event_bus().publish(
            DataPointRejected(
                data_point_id=dp.id,
                reviewed_by=ctx.user_id,
                organization_id=project.organization_id,
                target_user_ids=[dp.created_by] if dp.created_by else [],
                comment=comment or "",
            )
        )
        await invalidate_dashboard_project(dp.reporting_project_id)
        return {"id": dp.id, "status": dp.status, **gate_result}

    async def request_revision(self, dp_id: int, comment: str | None, ctx: RequestContext) -> dict:
        self._require_review_access(ctx)
        dp, project, _ = await get_data_point_for_ctx(self.dp_repo.session, dp_id, ctx)
        context = await self._build_gate_context(dp, project, ctx, "needs_revision", comment)
        gate_result = await self._check_gates("request_revision", context, ctx)

        dp = await self.dp_repo.update(dp_id, status="needs_revision", review_comment=comment)
        await create_data_point_version(
            self.dp_repo.session, dp, changed_by=ctx.user_id, change_reason="needs_revision"
        )
        await self._refresh_bound_item_statuses(dp.reporting_project_id, dp.id)
        await self._audit("data_point_revision_requested", dp_id, ctx, {"comment": comment})
        await get_event_bus().publish(
            DataPointRevisionRequested(
                data_point_id=dp.id,
                reviewed_by=ctx.user_id,
                organization_id=project.organization_id,
                target_user_ids=[dp.created_by] if dp.created_by else [],
                comment=comment or "",
            )
        )
        await invalidate_dashboard_project(dp.reporting_project_id)
        return {"id": dp.id, "status": dp.status, **gate_result}

    async def rollback(self, dp_id: int, comment: str | None, ctx: RequestContext) -> dict:
        self._require_rollback_access(ctx)
        dp, project, _ = await get_data_point_for_ctx(self.dp_repo.session, dp_id, ctx)
        context = await self._build_gate_context(dp, project, ctx, "draft", comment)
        gate_result = await self._check_gates("rollback_data_point", context, ctx)

        dp = await self.dp_repo.update(dp_id, status="draft", review_comment=comment)
        await create_data_point_version(
            self.dp_repo.session, dp, changed_by=ctx.user_id, change_reason="rolled_back"
        )
        await self._refresh_bound_item_statuses(dp.reporting_project_id, dp.id)
        await self._audit("data_point_rolled_back", dp_id, ctx, {"comment": comment})
        await get_event_bus().publish(
            DataPointRolledBack(
                data_point_id=dp.id,
                rolled_back_by=ctx.user_id,
                organization_id=project.organization_id,
                target_user_ids=[dp.created_by] if dp.created_by else [],
                reason=comment or "",
            )
        )
        await invalidate_dashboard_project(dp.reporting_project_id)
        return {"id": dp.id, "status": dp.status, **gate_result}

    async def gate_check(
        self,
        action: str,
        dp_id: int,
        ctx: RequestContext,
        comment: str | None = None,
        *,
        draft: dict | None = None,
        pending_evidence_count: int = 0,
    ) -> dict:
        dp, project, _ = await get_data_point_for_ctx(self.dp_repo.session, dp_id, ctx)
        target_map = {
            "submit_data_point": "submitted",
            "approve_data_point": "approved",
            "reject_data_point": "rejected",
            "request_revision": "needs_revision",
            "rollback_data_point": "draft",
        }
        target = target_map.get(action, "")
        context = await self._build_gate_context(dp, project, ctx, target, comment)
        context["data_point"] = self._build_preview_data_point(dp, draft)
        context["pending_evidence_count"] = pending_evidence_count
        result = await self.gate_engine.check(action, context)

        # Log gate check
        gate_log = {
            "action": action,
            "allowed": result.allowed,
            "failed_codes": [g.code for g in result.failed_gates],
            "warning_codes": [w.code for w in result.warnings],
        }
        if self.audit_repo:
            await self.audit_repo.log(
                entity_type="DataPoint",
                entity_id=dp_id,
                action="gate_check",
                user_id=ctx.user_id,
                organization_id=ctx.organization_id,
                changes=gate_log,
                performed_by_platform_admin=ctx.is_platform_admin,
            )

        return {
            "allowed": result.allowed,
            "failedGates": [
                {"code": g.code, "type": g.gate_type, "message": g.message, "severity": g.severity}
                for g in result.failed_gates
            ],
            "warnings": [
                {"code": w.code, "type": w.gate_type, "message": w.message}
                for w in result.warnings
            ],
        }
