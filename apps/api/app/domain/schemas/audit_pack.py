"""
Audit Pack schemas.

Audit pack export: report + evidence + comments in various formats.
"""

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from .common import BaseSchema


# =============================================================================
# Validation constants
# =============================================================================

VALID_FORMATS = {"report_pdf", "report_docx", "evidences_csv", "comments_csv", "evidence_summary_pdf", "audit_pack_zip"}
# Keep in sync with `JobStatus` enum values in `app.domain.models.enums`.
VALID_STATUSES = {"queued", "running", "partial_success", "failed", "success", "cancelled"}


# =============================================================================
# Audit Pack Request
# =============================================================================


class AuditPackRequest(BaseSchema):
    """Request to generate an audit pack."""

    formats: list[str] = Field(
        default=["report_pdf", "evidences_csv", "comments_csv", "audit_pack_zip"],
        description="Formats to generate",
    )
    locales: list[str] = Field(
        default_factory=list,
        description="Locales to include (empty = all enabled locales)",
    )
    include_internal_comments: bool = Field(
        default=False,
        description="Include internal (team-only) comments in export",
    )
    evidence_statuses: list[str] | None = Field(
        default=None,
        description="Filter evidence by statuses (null = all statuses)",
    )
    pdf_profile: str = Field(
        default="audit",
        description="PDF profile: audit or screen",
    )

    @field_validator("formats")
    @classmethod
    def validate_formats(cls, v: list[str]) -> list[str]:
        invalid = set(v) - VALID_FORMATS
        if invalid:
            raise ValueError(f"Invalid formats: {invalid}. Must be one of {VALID_FORMATS}")
        return v

    @field_validator("pdf_profile")
    @classmethod
    def validate_pdf_profile(cls, v: str) -> str:
        if v not in {"audit", "screen"}:
            raise ValueError("pdf_profile must be 'audit' or 'screen'")
        return v


# =============================================================================
# Audit Pack Job
# =============================================================================


class AuditPackJobDTO(BaseSchema):
    """Audit pack generation job."""

    job_id: UUID
    report_id: UUID
    company_id: UUID
    status: str = Field(description="Job status: queued, running, success, partial_success, failed, cancelled")
    formats: list[str]
    locales: list[str]
    include_internal_comments: bool
    evidence_statuses: list[str] | None
    pdf_profile: str
    # Job execution
    created_at_utc: datetime
    created_by: UUID | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    # Artifacts
    artifacts: list["AuditPackArtifactDTO"] = Field(default_factory=list)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {v}. Must be one of {VALID_STATUSES}")
        return v


class AuditPackArtifactDTO(BaseSchema):
    """Audit pack artifact (file ready for download)."""

    artifact_id: UUID
    job_id: UUID
    format: str = Field(description="Artifact format")
    locale: str | None = Field(default=None, description="Locale for this artifact (if applicable)")
    filename: str = Field(description="Filename for download")
    path: str | None = Field(default=None, description="Server path (internal)")
    size_bytes: int | None = Field(default=None, description="File size in bytes")
    sha256: str | None = Field(default=None, description="SHA256 checksum")
    created_at_utc: datetime
    # Warning flags
    attachments_excluded: bool = Field(
        default=False,
        description="Whether attachments were excluded due to size limit",
    )
    warning_message: str | None = Field(
        default=None,
        description="Warning message if graceful fallback occurred",
    )

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        if v not in VALID_FORMATS:
            raise ValueError(f"Invalid format: {v}. Must be one of {VALID_FORMATS}")
        return v


