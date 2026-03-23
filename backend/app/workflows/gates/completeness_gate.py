from app.workflows.gates.base import Gate, GateFailure


class RequirementIncompleteGate(Gate):
    """Reserved for aggregate completeness checks, not individual approval."""

    def applies_to(self, action: str) -> bool:
        return False

    async def evaluate(self, context: dict) -> GateFailure | None:
        item_statuses = context.get("item_statuses")
        item_status = context.get("item_status")

        if item_statuses:
            blocking_status = next(
                (
                    status
                    for status in item_statuses
                    if status not in ("complete", "not_applicable")
                ),
                None,
            )
            if blocking_status:
                return GateFailure(
                    code="REQUIREMENT_INCOMPLETE",
                    gate_type="completeness",
                    message=f"Requirement item status is '{blocking_status}', must be complete",
                    severity="blocker",
                )

        if item_status and item_status not in ("complete", "not_applicable"):
            return GateFailure(
                code="REQUIREMENT_INCOMPLETE",
                gate_type="completeness",
                message=f"Requirement item status is '{item_status}', must be complete",
                severity="blocker",
            )
        return None


class ProjectIncompleteGate(Gate):
    """Blocks review/publish/export if project not complete."""

    def applies_to(self, action: str) -> bool:
        return action in ("review_project", "publish_project", "start_export")

    async def evaluate(self, context: dict) -> GateFailure | None:
        completion_percent = context.get("completion_percent", 0)
        threshold = context.get("completion_threshold", 100)

        if completion_percent < threshold:
            return GateFailure(
                code="PROJECT_INCOMPLETE",
                gate_type="completeness",
                message=f"Project completion is {completion_percent}%, threshold is {threshold}%",
                severity="blocker",
            )
        return None
