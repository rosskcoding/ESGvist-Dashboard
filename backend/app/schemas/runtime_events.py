from typing import Literal

from pydantic import BaseModel, Field


class ClientRuntimeEventIn(BaseModel):
    event_type: Literal["api_error", "auth_expired", "ui_error", "unhandled_rejection"]
    level: Literal["info", "warning", "error"] = "error"
    message: str = Field(min_length=1, max_length=1000)
    path: str | None = Field(default=None, max_length=512)
    status: int | None = Field(default=None, ge=100, le=599)
    code: str | None = Field(default=None, max_length=128)
    request_id: str | None = Field(default=None, max_length=128)
    user_agent: str | None = Field(default=None, max_length=512)
    details: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class ClientRuntimeEventOut(BaseModel):
    accepted: bool = True
