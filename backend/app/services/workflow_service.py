import logging

from app.core.dependencies import RequestContext
from app.core.exceptions import AppError, GateBlockedError
from app.repositories.audit_repo import AuditRepository
from app.repositories.data_point_repo import DataPointRepository
from app.repositories.evidence_repo import EvidenceRepository
from app.workflows.gates.base import GateEngine
from app.workflows.gates.boundary_gate import (
    BoundaryInclusionGate,
    BoundaryNotDefinedGate,
    BoundaryNotLockedGate,
)
from app.workflows.gates.completeness_gate import ProjectIncompleteGate, RequirementIncompleteGate
from app.workflows.gates.data_gate import DataValidationGate
from app.workflows.gates.evidence_gate import EvidenceRequiredGate
from app.workflows.gates.review_gate import NoRequirementsGate, ProjectLockedGate, UnresolvedReviewGate
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
        ])

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
            )

    async def submit(self, dp_id: int, ctx: RequestContext, assignment_repo=None) -> dict:
        dp = await self.dp_repo.get_or_raise(dp_id)
        context = {"data_point": dp, "target_status": "submitted", "role": ctx.role}
        gate_result = await self._check_gates("submit_data_point", context, ctx)

        dp = await self.dp_repo.update(dp_id, status="submitted")
        await self._audit("data_point_submitted", dp_id, ctx)

        # Auto-transition to in_review if reviewer is assigned
        final_status = "submitted"
        if assignment_repo:
            from sqlalchemy import select
            from app.db.models.project import MetricAssignment

            q = select(MetricAssignment).where(
                MetricAssignment.reporting_project_id == dp.reporting_project_id,
                MetricAssignment.shared_element_id == dp.shared_element_id,
                MetricAssignment.reviewer_id.isnot(None),
            )
            result = await assignment_repo.session.execute(q)
            if result.scalar_one_or_none():
                dp = await self.dp_repo.update(dp_id, status="in_review")
                final_status = "in_review"

        return {"id": dp.id, "status": final_status, **gate_result}

    async def approve(self, dp_id: int, comment: str | None, ctx: RequestContext) -> dict:
        dp = await self.dp_repo.get_or_raise(dp_id)
        context = {"data_point": dp, "target_status": "approved", "role": ctx.role, "comment": comment}
        gate_result = await self._check_gates("approve_data_point", context, ctx)

        dp = await self.dp_repo.update(dp_id, status="approved", review_comment=comment)
        await self._audit("data_point_approved", dp_id, ctx, {"comment": comment})
        return {"id": dp.id, "status": dp.status, **gate_result}

    async def reject(self, dp_id: int, comment: str | None, ctx: RequestContext) -> dict:
        dp = await self.dp_repo.get_or_raise(dp_id)
        context = {"data_point": dp, "target_status": "rejected", "role": ctx.role, "comment": comment}
        gate_result = await self._check_gates("reject_data_point", context, ctx)

        dp = await self.dp_repo.update(dp_id, status="rejected", review_comment=comment)
        await self._audit("data_point_rejected", dp_id, ctx, {"comment": comment})
        return {"id": dp.id, "status": dp.status, **gate_result}

    async def request_revision(self, dp_id: int, comment: str | None, ctx: RequestContext) -> dict:
        dp = await self.dp_repo.get_or_raise(dp_id)
        context = {"data_point": dp, "target_status": "needs_revision", "role": ctx.role, "comment": comment}
        gate_result = await self._check_gates("request_revision", context, ctx)

        dp = await self.dp_repo.update(dp_id, status="needs_revision", review_comment=comment)
        await self._audit("data_point_revision_requested", dp_id, ctx, {"comment": comment})
        return {"id": dp.id, "status": dp.status, **gate_result}

    async def rollback(self, dp_id: int, comment: str | None, ctx: RequestContext) -> dict:
        dp = await self.dp_repo.get_or_raise(dp_id)
        context = {"data_point": dp, "target_status": "draft", "role": ctx.role, "comment": comment}
        gate_result = await self._check_gates("rollback_data_point", context, ctx)

        dp = await self.dp_repo.update(dp_id, status="draft", review_comment=comment)
        await self._audit("data_point_rolled_back", dp_id, ctx, {"comment": comment})
        return {"id": dp.id, "status": dp.status, **gate_result}

    async def gate_check(self, action: str, dp_id: int, ctx: RequestContext, comment: str | None = None) -> dict:
        dp = await self.dp_repo.get_or_raise(dp_id)
        target_map = {
            "submit_data_point": "submitted",
            "approve_data_point": "approved",
            "reject_data_point": "rejected",
            "request_revision": "needs_revision",
            "rollback_data_point": "draft",
        }
        target = target_map.get(action, "")
        context = {"data_point": dp, "target_status": target, "role": ctx.role, "comment": comment}
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
