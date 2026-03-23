from pydantic import BaseModel


class ErrorDetailOut(BaseModel):
    field: str | None = None
    reason: str
    expected: str | None = None


class ErrorBodyOut(BaseModel):
    code: str
    message: str
    details: list[ErrorDetailOut] = []
    requestId: str


class ErrorResponseOut(BaseModel):
    error: ErrorBodyOut


class HealthResponse(BaseModel):
    status: str
    checks: dict[str, str] = {}
    version: str = "0.1.0"
