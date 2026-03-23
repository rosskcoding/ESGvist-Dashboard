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
