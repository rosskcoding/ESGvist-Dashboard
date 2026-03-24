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


class NoReviewerAssignedGate(Gate):
    """Blocks transition to in_review when no reviewer is assigned.

    Checks ``reviewer_assigned`` boolean in context.  Applied after
    submit so the system can distinguish "no reviewer yet" from
    "reviewer assigned → auto-transition".
    """

    def applies_to(self, action: str) -> bool:
        return action in ("submit_data_point",)

    async def evaluate(self, context: dict) -> GateFailure | None:
        if not context.get("reviewer_assigned", True):
            return GateFailure(
                code="NO_REVIEWER_ASSIGNED",
                gate_type="review",
                message="No reviewer is assigned — data point will stay in 'submitted' until a reviewer is assigned",
                severity="warning",
            )
        return None


class NoAssignmentsGate(Gate):
    """Warns when starting a project without any metric assignments."""

    def applies_to(self, action: str) -> bool:
        return action in ("start_project",)

    async def evaluate(self, context: dict) -> GateFailure | None:
        assignment_count = context.get("assignment_count", 0)
        if assignment_count == 0:
            return GateFailure(
                code="NO_ASSIGNMENTS",
                gate_type="review",
                message="No metric assignments have been created — collectors won't see any work items",
                severity="warning",
            )
        return None


class UnsubmittedDataGate(Gate):
    """Warns when moving project to review while draft data points exist."""

    def applies_to(self, action: str) -> bool:
        return action in ("review_project",)

    async def evaluate(self, context: dict) -> GateFailure | None:
        draft_count = context.get("draft_data_point_count", 0)
        if draft_count > 0:
            return GateFailure(
                code="UNSUBMITTED_DATA",
                gate_type="review",
                message=f"{draft_count} data point(s) are still in draft and have not been submitted for review",
                severity="warning",
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
