from app.workflows.gates.base import Gate, GateFailure


class RequirementIncompleteGate(Gate):
    """Blocks approve if requirement item is incomplete."""

    def applies_to(self, action: str) -> bool:
        return action in ("approve_data_point",)

    async def evaluate(self, context: dict) -> GateFailure | None:
        item_status = context.get("item_status")
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
