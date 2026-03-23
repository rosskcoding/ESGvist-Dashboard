from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GateFailure:
    code: str
    gate_type: str
    message: str
    severity: str = "blocker"  # blocker | warning
    details: dict | None = None


@dataclass
class GateResult:
    allowed: bool
    failed_gates: list[GateFailure]
    warnings: list[GateFailure]


class Gate(ABC):
    @abstractmethod
    def applies_to(self, action: str) -> bool: ...

    @abstractmethod
    async def evaluate(self, context: dict) -> GateFailure | None: ...


class GateEngine:
    def __init__(self, gates: list[Gate]):
        self.gates = gates

    async def check(self, action: str, context: dict) -> GateResult:
        failed = []
        warnings = []

        for gate in self.gates:
            if not gate.applies_to(action):
                continue

            result = await gate.evaluate(context)
            if result is None:
                continue

            if result.severity == "blocker":
                failed.append(result)
            else:
                warnings.append(result)

        return GateResult(
            allowed=len(failed) == 0,
            failed_gates=failed,
            warnings=warnings,
        )
