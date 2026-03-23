from datetime import datetime

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: int
    organization_id: int | None = None
    user_id: int | None = None
    entity_type: str
    entity_id: int | None = None
    action: str
    changes: dict | None = None
    request_id: str | None = None
    performed_by_platform_admin: bool
    created_at: datetime | None = None


class AuditLogListOut(BaseModel):
    items: list[AuditLogOut]
    total: int


class AuditLogExportOut(BaseModel):
    format: str
    content_type: str
    filename: str
    content: dict | str
    total: int
