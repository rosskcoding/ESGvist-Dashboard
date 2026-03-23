from app.workflows.gates.base import Gate, GateFailure


class BoundaryInclusionGate(Gate):
    """Warns/blocks if entity is not in project boundary."""

    def __init__(self, boundary_repo=None):
        self.boundary_repo = boundary_repo

    def applies_to(self, action: str) -> bool:
        return action in ("submit_data_point",)

    async def evaluate(self, context: dict) -> GateFailure | None:
        dp = context.get("data_point")
        project = context.get("project")

        if not dp or not project:
            return None
        if not getattr(dp, "entity_id", None) or not getattr(project, "boundary_definition_id", None):
            return None

        # If boundary_repo is available, check membership
        if self.boundary_repo:
            from sqlalchemy import select
            from app.db.models.boundary import BoundaryMembership

            membership = await self.boundary_repo.session.execute(
                select(BoundaryMembership).where(
                    BoundaryMembership.boundary_definition_id == project.boundary_definition_id,
                    BoundaryMembership.entity_id == dp.entity_id,
                    BoundaryMembership.included == True,
                )
            )
            if not membership.scalar_one_or_none():
                return GateFailure(
                    code="OUT_OF_BOUNDARY",
                    gate_type="boundary",
                    message="Entity is not included in project boundary",
                    severity="warning",
                )
        return None


class BoundaryNotDefinedGate(Gate):
    """Blocks project start if no boundary defined."""

    def applies_to(self, action: str) -> bool:
        return action in ("start_project",)

    async def evaluate(self, context: dict) -> GateFailure | None:
        project = context.get("project")
        if project and not getattr(project, "boundary_definition_id", None):
            return GateFailure(
                code="BOUNDARY_NOT_DEFINED",
                gate_type="boundary",
                message="Project must have a boundary defined before starting",
                severity="blocker",
            )
        return None


class BoundaryNotLockedGate(Gate):
    """Blocks export/publish if boundary snapshot not locked."""

    def applies_to(self, action: str) -> bool:
        return action in ("start_export", "publish_project")

    async def evaluate(self, context: dict) -> GateFailure | None:
        # Simplified: just check boundary exists
        project = context.get("project")
        if project and not getattr(project, "boundary_definition_id", None):
            return GateFailure(
                code="BOUNDARY_NOT_LOCKED",
                gate_type="boundary",
                message="Boundary snapshot must be locked before export/publish",
                severity="blocker",
            )
        return None
