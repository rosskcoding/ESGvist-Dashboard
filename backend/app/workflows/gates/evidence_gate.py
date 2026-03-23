from app.workflows.gates.base import Gate, GateFailure


class EvidenceRequiredGate(Gate):
    """Blocks submit/approve if requires_evidence=true and no evidence attached."""

    def __init__(self, evidence_repo=None):
        self.evidence_repo = evidence_repo

    def applies_to(self, action: str) -> bool:
        return action in ("submit_data_point", "approve_data_point")

    async def evaluate(self, context: dict) -> GateFailure | None:
        dp = context.get("data_point")
        requirement_item = context.get("requirement_item")

        if not requirement_item or not getattr(requirement_item, "requires_evidence", False):
            return None

        if not dp or not self.evidence_repo:
            return None

        count = await self.evidence_repo.count_for_data_point(dp.id)
        if count == 0:
            return GateFailure(
                code="EVIDENCE_REQUIRED",
                gate_type="evidence",
                message="This data point requires supporting evidence before submission/approval",
                severity="blocker",
            )
        return None
