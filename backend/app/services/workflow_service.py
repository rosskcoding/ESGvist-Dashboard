from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
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


class WorkflowService:
    def __init__(
        self,
        dp_repo: DataPointRepository,
        evidence_repo: EvidenceRepository | None = None,
    ):
        self.dp_repo = dp_repo
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

    async def _check_gates(self, action: str, context: dict) -> dict:
        result = await self.gate_engine.check(action, context)
        if not result.allowed:
            raise AppError(
                code=result.failed_gates[0].code,
                status_code=422,
                message=result.failed_gates[0].message,
            )
        return {
            "warnings": [
                {"code": w.code, "type": w.gate_type, "message": w.message}
                for w in result.warnings
            ]
        }

    async def submit(self, dp_id: int, ctx: RequestContext, assignment_repo=None) -> dict:
        dp = await self.dp_repo.get_or_raise(dp_id)
        context = {"data_point": dp, "target_status": "submitted", "role": ctx.role}
        gate_result = await self._check_gates("submit_data_point", context)

        dp = await self.dp_repo.update(dp_id, status="submitted")

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
        gate_result = await self._check_gates("approve_data_point", context)

        dp = await self.dp_repo.update(dp_id, status="approved", review_comment=comment)
        return {"id": dp.id, "status": dp.status, **gate_result}

    async def reject(self, dp_id: int, comment: str | None, ctx: RequestContext) -> dict:
        dp = await self.dp_repo.get_or_raise(dp_id)
        context = {"data_point": dp, "target_status": "rejected", "role": ctx.role, "comment": comment}
        gate_result = await self._check_gates("reject_data_point", context)

        dp = await self.dp_repo.update(dp_id, status="rejected", review_comment=comment)
        return {"id": dp.id, "status": dp.status, **gate_result}

    async def request_revision(self, dp_id: int, comment: str | None, ctx: RequestContext) -> dict:
        dp = await self.dp_repo.get_or_raise(dp_id)
        context = {"data_point": dp, "target_status": "needs_revision", "role": ctx.role, "comment": comment}
        gate_result = await self._check_gates("request_revision", context)

        dp = await self.dp_repo.update(dp_id, status="needs_revision", review_comment=comment)
        return {"id": dp.id, "status": dp.status, **gate_result}

    async def rollback(self, dp_id: int, comment: str | None, ctx: RequestContext) -> dict:
        dp = await self.dp_repo.get_or_raise(dp_id)
        context = {"data_point": dp, "target_status": "draft", "role": ctx.role, "comment": comment}
        gate_result = await self._check_gates("rollback_data_point", context)

        dp = await self.dp_repo.update(dp_id, status="draft", review_comment=comment)
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
