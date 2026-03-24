from app.workflows.gates.base import Gate, GateFailure


class DataValidationGate(Gate):
    """Validates required fields before submit."""

    def applies_to(self, action: str) -> bool:
        return action in ("submit_data_point",)

    async def evaluate(self, context: dict) -> GateFailure | None:
        dp = context.get("data_point")
        if not dp:
            return None

        # Must have either numeric or text value
        if dp.numeric_value is None and not dp.text_value:
            return GateFailure(
                code="INVALID_DATA",
                gate_type="data",
                message="Data point must have a numeric or text value",
                severity="blocker",
            )
        return None


class InvalidValueTypeGate(Gate):
    """Validates that data point value matches the expected value_type from
    its requirement item / shared element.

    Context must include ``expected_value_type`` (str | None) from the
    requirement item.  If not supplied the gate is a no-op so callers
    that cannot resolve the type yet are unaffected.
    """

    _NUMERIC_TYPES = frozenset({"number", "integer", "decimal", "percent", "currency"})
    _TEXT_TYPES = frozenset({"text", "narrative", "string", "enum"})

    def applies_to(self, action: str) -> bool:
        return action in ("submit_data_point",)

    async def evaluate(self, context: dict) -> GateFailure | None:
        dp = context.get("data_point")
        expected = context.get("expected_value_type")
        if not dp or not expected:
            return None

        expected_lower = expected.lower()

        if expected_lower in self._NUMERIC_TYPES:
            if dp.numeric_value is None:
                return GateFailure(
                    code="INVALID_VALUE_TYPE",
                    gate_type="data",
                    message=f"Expected a numeric value (type '{expected}') but none provided",
                    severity="blocker",
                )
        elif expected_lower in self._TEXT_TYPES:
            if not dp.text_value:
                return GateFailure(
                    code="INVALID_VALUE_TYPE",
                    gate_type="data",
                    message=f"Expected a text value (type '{expected}') but none provided",
                    severity="blocker",
                )
        return None


class MissingDataGate(Gate):
    """Blocks assignment completion when bound data points have no value.

    Evaluates against ``missing_data_point_count`` in context (int).
    """

    def applies_to(self, action: str) -> bool:
        return action in ("complete_assignment",)

    async def evaluate(self, context: dict) -> GateFailure | None:
        missing = context.get("missing_data_point_count", 0)
        if missing > 0:
            return GateFailure(
                code="MISSING_DATA",
                gate_type="data",
                message=f"{missing} data point(s) still have no reported value",
                severity="blocker",
            )
        return None
