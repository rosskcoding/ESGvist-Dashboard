from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.repositories.data_point_repo import DataPointRepository
from app.workflows.gates.base import GateEngine
from app.workflows.gates.workflow_gate import (
    CommentRequiredGate,
    DataPointLockedGate,
    WorkflowTransitionGate,
)


class WorkflowService:
    def __init__(self, dp_repo: DataPointRepository):
        self.dp_repo = dp_repo
        self.gate_engine = GateEngine([
            WorkflowTransitionGate(),
            CommentRequiredGate(),
            DataPointLockedGate(),
        ])

    async def _check_gates(self, action: str, context: dict) -> None:
        result = await self.gate_engine.check(action, context)
        if not result.allowed:
            details = [
                {"code": g.code, "type": g.gate_type, "message": g.message}
                for g in result.failed_gates
            ]
            raise AppError(
                code=result.failed_gates[0].code,
                status_code=422,
                message=result.failed_gates[0].message,
            )

    async def submit(self, dp_id: int, ctx: RequestContext) -> dict:
        dp = await self.dp_repo.get_or_raise(dp_id)
        context = {"data_point": dp, "target_status": "submitted", "role": ctx.role}
        await self._check_gates("submit_data_point", context)

        dp = await self.dp_repo.update(dp_id, status="submitted")
        return {"id": dp.id, "status": dp.status}

    async def approve(self, dp_id: int, comment: str | None, ctx: RequestContext) -> dict:
        dp = await self.dp_repo.get_or_raise(dp_id)
        context = {"data_point": dp, "target_status": "approved", "role": ctx.role, "comment": comment}
        await self._check_gates("approve_data_point", context)

        dp = await self.dp_repo.update(dp_id, status="approved", review_comment=comment)
        return {"id": dp.id, "status": dp.status}

    async def reject(self, dp_id: int, comment: str | None, ctx: RequestContext) -> dict:
        dp = await self.dp_repo.get_or_raise(dp_id)
        context = {"data_point": dp, "target_status": "rejected", "role": ctx.role, "comment": comment}
        await self._check_gates("reject_data_point", context)

        dp = await self.dp_repo.update(dp_id, status="rejected", review_comment=comment)
        return {"id": dp.id, "status": dp.status}

    async def request_revision(self, dp_id: int, comment: str | None, ctx: RequestContext) -> dict:
        dp = await self.dp_repo.get_or_raise(dp_id)
        context = {"data_point": dp, "target_status": "needs_revision", "role": ctx.role, "comment": comment}
        await self._check_gates("request_revision", context)

        dp = await self.dp_repo.update(dp_id, status="needs_revision", review_comment=comment)
        return {"id": dp.id, "status": dp.status}

    async def rollback(self, dp_id: int, comment: str | None, ctx: RequestContext) -> dict:
        dp = await self.dp_repo.get_or_raise(dp_id)
        context = {"data_point": dp, "target_status": "draft", "role": ctx.role, "comment": comment}
        await self._check_gates("rollback_data_point", context)

        dp = await self.dp_repo.update(dp_id, status="draft", review_comment=comment)
        return {"id": dp.id, "status": dp.status}

    async def gate_check(self, action: str, dp_id: int, ctx: RequestContext, comment: str | None = None) -> dict:
        """Pre-flight gate check without actually transitioning."""
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
                {"code": g.code, "type": g.gate_type, "message": g.message}
                for g in result.failed_gates
            ],
            "warnings": [
                {"code": w.code, "type": w.gate_type, "message": w.message}
                for w in result.warnings
            ],
        }
