from app.workflows.gates.base import Gate, GateFailure


class EvidenceRequiredGate(Gate):
    """Blocks submit/approve if requires_evidence=true and no evidence attached."""

    def __init__(self, evidence_repo=None):
        self.evidence_repo = evidence_repo

    def applies_to(self, action: str) -> bool:
        return action in ("submit_data_point", "approve_data_point")

    async def evaluate(self, context: dict) -> GateFailure | None:
        dp = context.get("data_point")
        requirement_items = context.get("requirement_items")
        requirement_item = context.get("requirement_item")
        pending_evidence_count = max(int(context.get("pending_evidence_count", 0) or 0), 0)

        if requirement_items is None:
            requirement_items = [requirement_item] if requirement_item else []

        if not requirement_items or not any(
            getattr(item, "requires_evidence", False) for item in requirement_items
        ):
            return None

        if not dp or not self.evidence_repo:
            return None

        count = await self.evidence_repo.count_for_data_point(dp.id) + pending_evidence_count
        if count == 0:
            return GateFailure(
                code="EVIDENCE_REQUIRED",
                gate_type="evidence",
                message="This data point requires supporting evidence before submission/approval",
                severity="blocker",
            )
        return None
