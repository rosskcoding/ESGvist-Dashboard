from datetime import datetime

from pydantic import BaseModel, Field


class ExportJobCreate(BaseModel):
    export_format: str = Field(default="json", pattern=r"^(json|csv)$")
    report_type: str = Field(default="project_report", pattern=r"^(project_report|readiness_snapshot)$")


class ExportJobOut(BaseModel):
    id: int
    organization_id: int
    reporting_project_id: int
    requested_by_user_id: int | None = None
    report_type: str
    export_format: str
    status: str
    content_type: str | None = None
    artifact_name: str | None = None
    artifact_size_bytes: int | None = None
    checksum: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ExportJobListOut(BaseModel):
    items: list[ExportJobOut]
    total: int


class ExportArtifactOut(BaseModel):
    job_id: int
    export_format: str
    content_type: str
    artifact_name: str
    content: dict | str
    checksum: str | None = None
