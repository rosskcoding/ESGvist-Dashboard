from dataclasses import dataclass, field


@dataclass
class ErrorDetail:
    reason: str
    field: str | None = None
    expected: str | None = None


@dataclass
class AppError(Exception):
    code: str = "INTERNAL_ERROR"
    status_code: int = 500
    message: str = "An unexpected error occurred"
    details: list[ErrorDetail] = field(default_factory=list)

    def to_response(self, request_id: str) -> dict:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": [
                    {
                        "field": d.field,
                        "reason": d.reason,
                        "expected": d.expected,
                    }
                    for d in self.details
                ],
                "requestId": request_id,
            }
        }


@dataclass
class GateFailure:
    code: str
    gate_type: str
    message: str
    severity: str = "blocker"
    details: dict | None = None


@dataclass
class GateBlockedError(AppError):
    failed_gates: list[GateFailure] = field(default_factory=list)
    warnings: list[GateFailure] = field(default_factory=list)

    def to_response(self, request_id: str) -> dict:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": [
                    {
                        "code": g.code,
                        "type": g.gate_type,
                        "message": g.message,
                        "severity": g.severity,
                    }
                    for g in self.failed_gates
                ],
                "warnings": [
                    {
                        "code": w.code,
                        "type": w.gate_type,
                        "message": w.message,
                    }
                    for w in self.warnings
                ],
                "requestId": request_id,
            }
        }
