"""
AuditCheck schemas.

Audit checklist DTOs.
"""

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from .common import BaseSchema, TimestampSchema


# =============================================================================
# Enums for validation
# =============================================================================

VALID_TARGET_TYPES = {"report", "section", "block", "evidence_item"}
VALID_STATUSES = {"not_started", "in_review", "reviewed", "flagged", "needs_info"}
VALID_SEVERITIES = {"critical", "major", "minor", "info"}


# =============================================================================
# AuditCheck Schemas
# =============================================================================


class AuditCheckBase(BaseSchema):
    """Base audit check fields."""

    target_type: str = Field(description="Target type: report, section, block, evidence_item")
    target_id: UUID = Field(description="ID of the target entity")
    status: str = Field(default="not_started", description="Check status")
    severity: str | None = Field(default=None, description="Severity if flagged")
    comment: str | None = Field(default=None, max_length=5000)

    @field_validator("target_type")
    @classmethod
    def validate_target_type(cls, v: str) -> str:
        if v not in VALID_TARGET_TYPES:
            raise ValueError(f"Invalid target_type: {v}. Must be one of {VALID_TARGET_TYPES}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {v}. Must be one of {VALID_STATUSES}")
        return v

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_SEVERITIES:
            raise ValueError(f"Invalid severity: {v}. Must be one of {VALID_SEVERITIES}")
        return v


class AuditCheckCreate(AuditCheckBase):
    """Schema for creating an audit check."""

    source_snapshot_id: UUID | None = Field(
        default=None,
        description="Source snapshot ID. NULL = live review",
    )


class AuditCheckUpdate(BaseSchema):
    """Schema for updating an audit check (upsert)."""

    target_type: str
    target_id: UUID
    status: str
    severity: str | None = None
    comment: str | None = Field(default=None, max_length=5000)
    source_snapshot_id: UUID | None = None

    @field_validator("target_type")
    @classmethod
    def validate_target_type(cls, v: str) -> str:
        if v not in VALID_TARGET_TYPES:
            raise ValueError(f"Invalid target_type: {v}. Must be one of {VALID_TARGET_TYPES}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {v}. Must be one of {VALID_STATUSES}")
        return v

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_SEVERITIES:
            raise ValueError(f"Invalid severity: {v}. Must be one of {VALID_SEVERITIES}")
        return v


class AuditCheckDTO(AuditCheckBase, TimestampSchema):
    """Audit check data transfer object (response)."""

    check_id: UUID
    company_id: UUID
    report_id: UUID
    source_snapshot_id: UUID | None = None
    auditor_id: UUID
    reviewed_at_utc: datetime | None = None


class AuditCheckWithAuditorDTO(AuditCheckDTO):
    """Audit check with auditor details."""

    auditor_name: str
    auditor_email: str


# =============================================================================
# Query/Filter Schemas
# =============================================================================


class AuditCheckFilter(BaseSchema):
    """Filter for querying audit checks."""

    target_type: str | None = None
    target_id: UUID | None = None
    status: str | None = None
    severity: str | None = None
    auditor_id: UUID | None = None
    source_snapshot_id: UUID | None = None


# =============================================================================
# Summary Schemas
# =============================================================================


class AuditSummaryDTO(BaseSchema):
    """Audit readiness summary for release gate."""

    report_id: UUID
    source_snapshot_id: UUID | None = None
    basis: str = Field(description="snapshot or live")

    # Coverage
    total_sections: int
    reviewed_sections: int
    coverage_percent: float

    # Issue counts
    critical_count: int
    major_count: int
    minor_count: int
    info_count: int

    # Status breakdown
    by_status: dict[str, int]  # {"reviewed": 10, "flagged": 2, ...}

    # Evidence completeness (optional)
    evidence_count: int = 0
    required_evidence_count: int = 0  # If you track required evidence

    # Flags
    has_critical: bool
    requires_rationale: bool


class AuditFinalizeRequest(BaseSchema):
    """Request to finalize section/report audit."""

    comment: str | None = Field(default=None, max_length=2000)


class SectionAuditStatusDTO(BaseSchema):
    """Audit status for a single section."""

    section_id: UUID
    section_title: str
    total_blocks: int
    reviewed_blocks: int
    flagged_blocks: int
    coverage_percent: float
    has_issues: bool
    max_severity: str | None = None  # Most severe issue in section


