from app.workflows.gates.base import Gate, GateFailure


class BoundaryInclusionGate(Gate):
    """Warns if data point's entity is not in the project boundary.

    Uses ``boundary_entity_included`` (bool | None) from context,
    which is resolved by ``_build_gate_context()`` in WorkflowService.
    No repo dependency needed — the service does the lookup.
    """

    def applies_to(self, action: str) -> bool:
        return action in ("submit_data_point",)

    async def evaluate(self, context: dict) -> GateFailure | None:
        included = context.get("boundary_entity_included")
        # None means no entity_id or no boundary — skip
        if included is None:
            return None
        if not included:
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
        project = context.get("project")
        if project and not getattr(project, "boundary_definition_id", None):
            return GateFailure(
                code="BOUNDARY_NOT_LOCKED",
                gate_type="boundary",
                message="Boundary snapshot must be locked before export/publish",
                severity="blocker",
            )
        if project and not context.get("boundary_snapshot_locked", False):
            return GateFailure(
                code="BOUNDARY_NOT_LOCKED",
                gate_type="boundary",
                message="Boundary snapshot must be created and match the active project boundary",
                severity="blocker",
            )
        return None


class EmptyBoundaryGate(Gate):
    """Blocks snapshot creation if boundary has no included entities."""

    def applies_to(self, action: str) -> bool:
        return action in ("lock_snapshot", "create_snapshot")

    async def evaluate(self, context: dict) -> GateFailure | None:
        included_count = context.get("included_entity_count", 0)
        if included_count == 0:
            return GateFailure(
                code="EMPTY_BOUNDARY",
                gate_type="boundary",
                message="Boundary must include at least one entity before a snapshot can be created",
                severity="blocker",
            )
        return None


class SnapshotAlreadyLockedGate(Gate):
    """Warns when overwriting an existing locked snapshot.

    Uses severity ``warning`` — the action is still allowed but the caller
    should notify the user that the previous snapshot will be replaced.
    For published projects, snapshot overwrite is separately blocked by
    ``BoundaryPolicy.snapshot_immutable()``.
    """

    def applies_to(self, action: str) -> bool:
        return action in ("lock_snapshot", "create_snapshot")

    async def evaluate(self, context: dict) -> GateFailure | None:
        if context.get("existing_snapshot_locked", False):
            return GateFailure(
                code="SNAPSHOT_ALREADY_LOCKED",
                gate_type="boundary",
                message="A locked snapshot already exists and will be replaced",
                severity="warning",
            )
        return None
