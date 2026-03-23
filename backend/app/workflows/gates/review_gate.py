from app.workflows.gates.base import Gate, GateFailure


class ReviewNotCompletedGate(Gate):
    """Blocks publish/export if no review has been performed."""

    def applies_to(self, action: str) -> bool:
        return action in ("publish_project", "start_export")

    async def evaluate(self, context: dict) -> GateFailure | None:
        reviewed_count = context.get("reviewed_count", 0)
        total_count = context.get("total_data_point_count", 0)
        if total_count > 0 and reviewed_count == 0:
            return GateFailure(
                code="REVIEW_NOT_COMPLETED",
                gate_type="review",
                message="No data points have been reviewed — at least one review is required",
                severity="blocker",
            )
        return None


class UnresolvedReviewGate(Gate):
    """Blocks publish if there are unresolved review items."""

    def applies_to(self, action: str) -> bool:
        return action in ("publish_project",)

    async def evaluate(self, context: dict) -> GateFailure | None:
        unresolved_count = context.get("unresolved_review_count", 0)
        if unresolved_count > 0:
            return GateFailure(
                code="UNRESOLVED_REVIEW",
                gate_type="review",
                message=f"{unresolved_count} data points have unresolved review status",
                severity="blocker",
            )
        return None


class NoRequirementsGate(Gate):
    """Blocks project start if no standards selected."""

    def applies_to(self, action: str) -> bool:
        return action in ("start_project",)

    async def evaluate(self, context: dict) -> GateFailure | None:
        standard_count = context.get("standard_count", 0)
        if standard_count == 0:
            return GateFailure(
                code="NO_REQUIREMENTS",
                gate_type="review",
                message="Project must have at least one standard before starting",
                severity="blocker",
            )
        return None


class ProjectLockedGate(Gate):
    """Blocks edits on published project."""

    def applies_to(self, action: str) -> bool:
        return action in (
            "edit_data_point", "submit_data_point", "rollback_data_point",
            "create_assignment", "apply_boundary",
        )

    async def evaluate(self, context: dict) -> GateFailure | None:
        project = context.get("project")
        if project and getattr(project, "status", "") == "published":
            return GateFailure(
                code="PROJECT_LOCKED",
                gate_type="workflow",
                message="Project is published — editing is blocked",
                severity="blocker",
            )
        return None
