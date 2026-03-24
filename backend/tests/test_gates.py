"""Tests for the 7 new gate codes added per TZ-WorkflowGateMatrix.md audit.

Each gate is tested in isolation via direct evaluate() calls and via
GateEngine integration to verify applies_to + severity classification.
"""

import pytest
from types import SimpleNamespace

from app.workflows.gates.base import GateEngine
from app.workflows.gates.data_gate import (
    DataValidationGate,
    InvalidValueTypeGate,
    MissingDataGate,
)
from app.workflows.gates.boundary_gate import (
    EmptyBoundaryGate,
    SnapshotAlreadyLockedGate,
)
from app.workflows.gates.review_gate import (
    NoAssignmentsGate,
    NoReviewerAssignedGate,
    UnsubmittedDataGate,
)


# ─── Helpers ──────────────────────────────────────────────────────────

def _dp(**kwargs):
    """Minimal data point namespace for gate context."""
    defaults = {"numeric_value": None, "text_value": None, "status": "draft"}
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _project(**kwargs):
    defaults = {"status": "draft", "boundary_definition_id": 1}
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ═══════════════════════════════════════════════════════════════════════
# 1. INVALID_VALUE_TYPE
# ═══════════════════════════════════════════════════════════════════════

class TestInvalidValueTypeGate:
    gate = InvalidValueTypeGate()

    @pytest.mark.asyncio
    async def test_applies_to_submit(self):
        assert self.gate.applies_to("submit_data_point")
        assert not self.gate.applies_to("approve_data_point")

    @pytest.mark.asyncio
    async def test_numeric_type_with_no_numeric_value_blocks(self):
        result = await self.gate.evaluate({
            "data_point": _dp(text_value="some text"),
            "expected_value_type": "number",
        })
        assert result is not None
        assert result.code == "INVALID_VALUE_TYPE"
        assert result.severity == "blocker"

    @pytest.mark.asyncio
    async def test_numeric_type_with_numeric_value_passes(self):
        result = await self.gate.evaluate({
            "data_point": _dp(numeric_value=42.0),
            "expected_value_type": "number",
        })
        assert result is None

    @pytest.mark.asyncio
    async def test_text_type_with_no_text_value_blocks(self):
        result = await self.gate.evaluate({
            "data_point": _dp(numeric_value=100),
            "expected_value_type": "text",
        })
        assert result is not None
        assert result.code == "INVALID_VALUE_TYPE"

    @pytest.mark.asyncio
    async def test_text_type_with_text_value_passes(self):
        result = await self.gate.evaluate({
            "data_point": _dp(text_value="hello"),
            "expected_value_type": "narrative",
        })
        assert result is None

    @pytest.mark.asyncio
    async def test_no_expected_type_is_noop(self):
        result = await self.gate.evaluate({
            "data_point": _dp(),
            "expected_value_type": None,
        })
        assert result is None

    @pytest.mark.asyncio
    async def test_no_data_point_is_noop(self):
        result = await self.gate.evaluate({"expected_value_type": "number"})
        assert result is None

    @pytest.mark.asyncio
    async def test_integer_type_treated_as_numeric(self):
        result = await self.gate.evaluate({
            "data_point": _dp(),
            "expected_value_type": "integer",
        })
        assert result is not None
        assert result.code == "INVALID_VALUE_TYPE"

    @pytest.mark.asyncio
    async def test_enum_type_treated_as_text(self):
        result = await self.gate.evaluate({
            "data_point": _dp(),
            "expected_value_type": "enum",
        })
        assert result is not None
        assert result.code == "INVALID_VALUE_TYPE"


# ═══════════════════════════════════════════════════════════════════════
# 2. MISSING_DATA
# ═══════════════════════════════════════════════════════════════════════

class TestMissingDataGate:
    gate = MissingDataGate()

    @pytest.mark.asyncio
    async def test_applies_to_complete_assignment(self):
        assert self.gate.applies_to("complete_assignment")
        assert not self.gate.applies_to("submit_data_point")

    @pytest.mark.asyncio
    async def test_missing_data_blocks(self):
        result = await self.gate.evaluate({"missing_data_point_count": 3})
        assert result is not None
        assert result.code == "MISSING_DATA"
        assert result.severity == "blocker"
        assert "3" in result.message

    @pytest.mark.asyncio
    async def test_no_missing_data_passes(self):
        result = await self.gate.evaluate({"missing_data_point_count": 0})
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_key_defaults_to_zero(self):
        result = await self.gate.evaluate({})
        assert result is None


# ═══════════════════════════════════════════════════════════════════════
# 3. EMPTY_BOUNDARY
# ═══════════════════════════════════════════════════════════════════════

class TestEmptyBoundaryGate:
    gate = EmptyBoundaryGate()

    @pytest.mark.asyncio
    async def test_applies_to_snapshot_actions(self):
        assert self.gate.applies_to("lock_snapshot")
        assert self.gate.applies_to("create_snapshot")
        assert not self.gate.applies_to("start_project")

    @pytest.mark.asyncio
    async def test_zero_entities_blocks(self):
        result = await self.gate.evaluate({"included_entity_count": 0})
        assert result is not None
        assert result.code == "EMPTY_BOUNDARY"
        assert result.severity == "blocker"

    @pytest.mark.asyncio
    async def test_entities_present_passes(self):
        result = await self.gate.evaluate({"included_entity_count": 5})
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_key_defaults_to_zero_blocks(self):
        result = await self.gate.evaluate({})
        assert result is not None
        assert result.code == "EMPTY_BOUNDARY"


# ═══════════════════════════════════════════════════════════════════════
# 4. SNAPSHOT_ALREADY_LOCKED
# ═══════════════════════════════════════════════════════════════════════

class TestSnapshotAlreadyLockedGate:
    gate = SnapshotAlreadyLockedGate()

    @pytest.mark.asyncio
    async def test_applies_to_snapshot_actions(self):
        assert self.gate.applies_to("lock_snapshot")
        assert self.gate.applies_to("create_snapshot")
        assert not self.gate.applies_to("publish_project")

    @pytest.mark.asyncio
    async def test_existing_locked_snapshot_warns(self):
        result = await self.gate.evaluate({"existing_snapshot_locked": True})
        assert result is not None
        assert result.code == "SNAPSHOT_ALREADY_LOCKED"
        assert result.severity == "warning"

    @pytest.mark.asyncio
    async def test_no_existing_snapshot_passes(self):
        result = await self.gate.evaluate({"existing_snapshot_locked": False})
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_key_passes(self):
        result = await self.gate.evaluate({})
        assert result is None


# ═══════════════════════════════════════════════════════════════════════
# 5. NO_REVIEWER_ASSIGNED
# ═══════════════════════════════════════════════════════════════════════

class TestNoReviewerAssignedGate:
    gate = NoReviewerAssignedGate()

    @pytest.mark.asyncio
    async def test_applies_to_submit(self):
        assert self.gate.applies_to("submit_data_point")
        assert not self.gate.applies_to("approve_data_point")

    @pytest.mark.asyncio
    async def test_no_reviewer_warns(self):
        result = await self.gate.evaluate({"reviewer_assigned": False})
        assert result is not None
        assert result.code == "NO_REVIEWER_ASSIGNED"
        assert result.severity == "warning"

    @pytest.mark.asyncio
    async def test_reviewer_present_passes(self):
        result = await self.gate.evaluate({"reviewer_assigned": True})
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_key_defaults_to_true(self):
        """Backwards compat: if context doesn't include the key, pass."""
        result = await self.gate.evaluate({})
        assert result is None


# ═══════════════════════════════════════════════════════════════════════
# 6. NO_ASSIGNMENTS
# ═══════════════════════════════════════════════════════════════════════

class TestNoAssignmentsGate:
    gate = NoAssignmentsGate()

    @pytest.mark.asyncio
    async def test_applies_to_start_project(self):
        assert self.gate.applies_to("start_project")
        assert not self.gate.applies_to("publish_project")

    @pytest.mark.asyncio
    async def test_no_assignments_warns(self):
        result = await self.gate.evaluate({"assignment_count": 0})
        assert result is not None
        assert result.code == "NO_ASSIGNMENTS"
        assert result.severity == "warning"

    @pytest.mark.asyncio
    async def test_assignments_present_passes(self):
        result = await self.gate.evaluate({"assignment_count": 10})
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_key_defaults_to_zero_warns(self):
        result = await self.gate.evaluate({})
        assert result is not None
        assert result.code == "NO_ASSIGNMENTS"


# ═══════════════════════════════════════════════════════════════════════
# 7. UNSUBMITTED_DATA
# ═══════════════════════════════════════════════════════════════════════

class TestUnsubmittedDataGate:
    gate = UnsubmittedDataGate()

    @pytest.mark.asyncio
    async def test_applies_to_review_project(self):
        assert self.gate.applies_to("review_project")
        assert not self.gate.applies_to("start_project")

    @pytest.mark.asyncio
    async def test_draft_data_warns(self):
        result = await self.gate.evaluate({"draft_data_point_count": 5})
        assert result is not None
        assert result.code == "UNSUBMITTED_DATA"
        assert result.severity == "warning"
        assert "5" in result.message

    @pytest.mark.asyncio
    async def test_no_draft_data_passes(self):
        result = await self.gate.evaluate({"draft_data_point_count": 0})
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_key_defaults_to_zero(self):
        result = await self.gate.evaluate({})
        assert result is None


# ═══════════════════════════════════════════════════════════════════════
# Integration: GateEngine with all new gates
# ═══════════════════════════════════════════════════════════════════════

class TestGateEngineIntegration:
    """Verify new gates integrate correctly with GateEngine."""

    engine = GateEngine([
        InvalidValueTypeGate(),
        MissingDataGate(),
        EmptyBoundaryGate(),
        SnapshotAlreadyLockedGate(),
        NoReviewerAssignedGate(),
        NoAssignmentsGate(),
        UnsubmittedDataGate(),
    ])

    @pytest.mark.asyncio
    async def test_submit_with_wrong_value_type_and_no_reviewer(self):
        """Submit triggers both INVALID_VALUE_TYPE (blocker) and
        NO_REVIEWER_ASSIGNED (warning)."""
        result = await self.engine.check("submit_data_point", {
            "data_point": _dp(),
            "expected_value_type": "number",
            "reviewer_assigned": False,
        })
        assert not result.allowed
        codes = {f.code for f in result.failed_gates}
        warning_codes = {w.code for w in result.warnings}
        assert "INVALID_VALUE_TYPE" in codes
        assert "NO_REVIEWER_ASSIGNED" in warning_codes

    @pytest.mark.asyncio
    async def test_start_project_with_no_assignments_warns_but_allows(self):
        result = await self.engine.check("start_project", {
            "assignment_count": 0,
        })
        assert result.allowed  # warning, not blocker
        warning_codes = {w.code for w in result.warnings}
        assert "NO_ASSIGNMENTS" in warning_codes

    @pytest.mark.asyncio
    async def test_review_project_with_drafts_warns_but_allows(self):
        result = await self.engine.check("review_project", {
            "draft_data_point_count": 3,
        })
        assert result.allowed
        warning_codes = {w.code for w in result.warnings}
        assert "UNSUBMITTED_DATA" in warning_codes

    @pytest.mark.asyncio
    async def test_snapshot_with_empty_boundary_blocks(self):
        result = await self.engine.check("create_snapshot", {
            "included_entity_count": 0,
        })
        assert not result.allowed
        codes = {f.code for f in result.failed_gates}
        assert "EMPTY_BOUNDARY" in codes

    @pytest.mark.asyncio
    async def test_snapshot_with_existing_lock_warns(self):
        result = await self.engine.check("lock_snapshot", {
            "included_entity_count": 5,
            "existing_snapshot_locked": True,
        })
        assert result.allowed  # warning, not blocker
        warning_codes = {w.code for w in result.warnings}
        assert "SNAPSHOT_ALREADY_LOCKED" in warning_codes

    @pytest.mark.asyncio
    async def test_complete_assignment_with_missing_data_blocks(self):
        result = await self.engine.check("complete_assignment", {
            "missing_data_point_count": 2,
        })
        assert not result.allowed
        codes = {f.code for f in result.failed_gates}
        assert "MISSING_DATA" in codes

    @pytest.mark.asyncio
    async def test_unrelated_action_triggers_nothing(self):
        result = await self.engine.check("approve_data_point", {})
        assert result.allowed
        assert len(result.failed_gates) == 0
        assert len(result.warnings) == 0


class TestServiceImports:
    """Verify gates are properly imported and wired in services."""

    def test_workflow_service_has_new_gates(self):
        from app.services.workflow_service import WorkflowService
        from app.repositories.data_point_repo import DataPointRepository
        # Can't instantiate without session, but can check gate types
        import inspect
        source = inspect.getsource(WorkflowService.__init__)
        assert "InvalidValueTypeGate" in source
        assert "MissingDataGate" in source
        assert "NoReviewerAssignedGate" in source

    def test_project_service_has_new_gates(self):
        from app.services.project_service import ProjectService
        import inspect
        source = inspect.getsource(ProjectService.__init__)
        assert "NoAssignmentsGate" in source
        assert "UnsubmittedDataGate" in source
