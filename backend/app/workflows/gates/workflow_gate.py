from app.domain.workflow_state import can_transition, is_editable, requires_comment
from app.workflows.gates.base import Gate, GateFailure


class WorkflowTransitionGate(Gate):
    def applies_to(self, action: str) -> bool:
        return action in (
            "submit_data_point", "approve_data_point", "reject_data_point",
            "request_revision", "rollback_data_point",
        )

    async def evaluate(self, context: dict) -> GateFailure | None:
        dp = context.get("data_point")
        target = context.get("target_status")
        role = context.get("role")

        if not dp or not target or not role:
            return None

        if not can_transition(dp.status, target, role):
            return GateFailure(
                code="INVALID_WORKFLOW_TRANSITION",
                gate_type="workflow",
                message=f"Transition from '{dp.status}' to '{target}' not allowed for role '{role}'",
            )
        return None


class CommentRequiredGate(Gate):
    def applies_to(self, action: str) -> bool:
        return action in ("reject_data_point", "request_revision", "rollback_data_point")

    async def evaluate(self, context: dict) -> GateFailure | None:
        dp = context.get("data_point")
        target = context.get("target_status")
        comment = context.get("comment")

        if dp and target and requires_comment(dp.status, target) and not comment:
            return GateFailure(
                code="REVIEW_COMMENT_REQUIRED",
                gate_type="workflow",
                message="Comment is required for this action",
            )
        return None


class DataPointLockedGate(Gate):
    def applies_to(self, action: str) -> bool:
        return action in ("edit_data_point", "unlink_evidence")

    async def evaluate(self, context: dict) -> GateFailure | None:
        dp = context.get("data_point")
        if dp and not is_editable(dp.status):
            return GateFailure(
                code="DATA_POINT_LOCKED",
                gate_type="workflow",
                message=f"Cannot edit data point in status '{dp.status}'",
            )
        return None


class LockedStateGate(Gate):
    """Blocks reopening a published project."""

    def applies_to(self, action: str) -> bool:
        return action in ("reopen_project", "unpublish_project")

    async def evaluate(self, context: dict) -> GateFailure | None:
        project = context.get("project")
        if project and getattr(project, "status", "") == "published":
            return GateFailure(
                code="LOCKED_STATE",
                gate_type="workflow",
                message="Project is published and cannot be reopened",
                severity="blocker",
            )
        return None


class ExportInProgressGate(Gate):
    """Blocks export queueing when another export job is already active."""

    def applies_to(self, action: str) -> bool:
        return action in ("start_export",)

    async def evaluate(self, context: dict) -> GateFailure | None:
        active_export_count = context.get("active_export_count", 0)
        if active_export_count > 0:
            return GateFailure(
                code="EXPORT_IN_PROGRESS",
                gate_type="workflow",
                message="An export job is already queued or running for this project",
                severity="blocker",
            )
        return None
