"""
EvidenceItem schemas.

Audit evidence storage DTOs.

Enhanced workflow fields:
- status (provided/reviewed/issue/resolved)
- sub_anchor_* for granular anchoring (table/chart/datapoint/audit_check_item)
- owner_user_id for assignment
- period_start/period_end for evidence time range
- version_label for tracking
- deleted_at/deleted_by for soft delete
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from .common import BaseSchema, TimestampSchema


# =============================================================================
# Enums for validation
# =============================================================================

VALID_SCOPE_TYPES = {"report", "section", "block"}
VALID_EVIDENCE_TYPES = {"file", "link", "note"}
VALID_VISIBILITY = {"team", "audit", "restricted"}
VALID_SOURCES = {"internal", "external"}
VALID_LOCALES = {"ru", "en", "kk", "de", "fr", "ar", "es", "nl", "it"}
VALID_STATUSES = {"provided", "reviewed", "issue", "resolved"}
VALID_SUB_ANCHOR_TYPES = {"table", "chart", "datapoint", "audit_check_item"}


# =============================================================================
# EvidenceItem Schemas
# =============================================================================


class EvidenceItemBase(BaseSchema):
    """Base evidence item fields."""

    report_id: UUID = Field(description="Report ID this evidence belongs to")
    scope_type: str = Field(description="Scope type: report, section, or block")
    scope_id: UUID = Field(description="ID of the scoped entity")
    locale: str | None = Field(default=None, description="Optional locale binding")
    type: str = Field(description="Evidence type: file, link, or note")
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    tags: list[str] | None = None
    source: str | None = Field(default=None, description="internal or external")
    visibility: str = Field(default="team", description="Visibility: team, audit, restricted")

    @field_validator("scope_type")
    @classmethod
    def validate_scope_type(cls, v: str) -> str:
        if v not in VALID_SCOPE_TYPES:
            raise ValueError(f"Invalid scope_type: {v}. Must be one of {VALID_SCOPE_TYPES}")
        return v

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in VALID_EVIDENCE_TYPES:
            raise ValueError(f"Invalid type: {v}. Must be one of {VALID_EVIDENCE_TYPES}")
        return v

    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, v: str) -> str:
        if v not in VALID_VISIBILITY:
            raise ValueError(f"Invalid visibility: {v}. Must be one of {VALID_VISIBILITY}")
        return v

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_SOURCES:
            raise ValueError(f"Invalid source: {v}. Must be one of {VALID_SOURCES}")
        return v

    @field_validator("locale")
    @classmethod
    def validate_locale(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_LOCALES:
            raise ValueError(f"Invalid locale: {v}. Must be one of {VALID_LOCALES}")
        return v


class EvidenceFileCreate(EvidenceItemBase):
    """Schema for creating file evidence."""

    type: str = "file"
    asset_id: UUID = Field(description="ID of uploaded asset")
    # Workflow fields
    status: str = Field(default="provided", description="Evidence status")
    sub_anchor_type: str | None = Field(default=None, description="table, chart, datapoint, or audit_check_item")
    sub_anchor_key: str | None = Field(default=None, max_length=255, description="Technical key for sub-anchor")
    sub_anchor_label: str | None = Field(default=None, max_length=255, description="Human-readable label")
    owner_user_id: UUID | None = Field(default=None, description="User responsible for this evidence")
    period_start: date | None = Field(default=None, description="Evidence period start date")
    period_end: date | None = Field(default=None, description="Evidence period end date")
    version_label: str | None = Field(default=None, max_length=100, description="Version label")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {v}. Must be one of {VALID_STATUSES}")
        return v

    @field_validator("sub_anchor_type")
    @classmethod
    def validate_sub_anchor_type(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_SUB_ANCHOR_TYPES:
            raise ValueError(f"Invalid sub_anchor_type: {v}. Must be one of {VALID_SUB_ANCHOR_TYPES}")
        return v


class EvidenceLinkCreate(EvidenceItemBase):
    """Schema for creating link evidence."""

    type: str = "link"
    url: str = Field(min_length=1, max_length=2000, description="External URL")
    # Workflow fields
    status: str = Field(default="provided", description="Evidence status")
    sub_anchor_type: str | None = Field(default=None, description="table, chart, datapoint, or audit_check_item")
    sub_anchor_key: str | None = Field(default=None, max_length=255, description="Technical key for sub-anchor")
    sub_anchor_label: str | None = Field(default=None, max_length=255, description="Human-readable label")
    owner_user_id: UUID | None = Field(default=None, description="User responsible for this evidence")
    period_start: date | None = Field(default=None, description="Evidence period start date")
    period_end: date | None = Field(default=None, description="Evidence period end date")
    version_label: str | None = Field(default=None, max_length=100, description="Version label")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {v}. Must be one of {VALID_STATUSES}")
        return v

    @field_validator("sub_anchor_type")
    @classmethod
    def validate_sub_anchor_type(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_SUB_ANCHOR_TYPES:
            raise ValueError(f"Invalid sub_anchor_type: {v}. Must be one of {VALID_SUB_ANCHOR_TYPES}")
        return v


class EvidenceNoteCreate(EvidenceItemBase):
    """Schema for creating note evidence."""

    type: str = "note"
    note_md: str = Field(min_length=1, max_length=10000, description="Markdown note content")
    # Workflow fields
    status: str = Field(default="provided", description="Evidence status")
    sub_anchor_type: str | None = Field(default=None, description="table, chart, datapoint, or audit_check_item")
    sub_anchor_key: str | None = Field(default=None, max_length=255, description="Technical key for sub-anchor")
    sub_anchor_label: str | None = Field(default=None, max_length=255, description="Human-readable label")
    owner_user_id: UUID | None = Field(default=None, description="User responsible for this evidence")
    period_start: date | None = Field(default=None, description="Evidence period start date")
    period_end: date | None = Field(default=None, description="Evidence period end date")
    version_label: str | None = Field(default=None, max_length=100, description="Version label")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {v}. Must be one of {VALID_STATUSES}")
        return v

    @field_validator("sub_anchor_type")
    @classmethod
    def validate_sub_anchor_type(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_SUB_ANCHOR_TYPES:
            raise ValueError(f"Invalid sub_anchor_type: {v}. Must be one of {VALID_SUB_ANCHOR_TYPES}")
        return v


class EvidenceItemCreate(EvidenceItemBase):
    """Generic schema for creating evidence (use type-specific ones when possible)."""

    asset_id: UUID | None = None
    url: str | None = Field(default=None, max_length=2000)
    note_md: str | None = Field(default=None, max_length=10000)
    # Workflow fields
    status: str = Field(default="provided", description="Evidence status")
    sub_anchor_type: str | None = Field(default=None, description="table, chart, datapoint, or audit_check_item")
    sub_anchor_key: str | None = Field(default=None, max_length=255, description="Technical key for sub-anchor")
    sub_anchor_label: str | None = Field(default=None, max_length=255, description="Human-readable label")
    owner_user_id: UUID | None = Field(default=None, description="User responsible for this evidence")
    period_start: date | None = Field(default=None, description="Evidence period start date")
    period_end: date | None = Field(default=None, description="Evidence period end date")
    version_label: str | None = Field(default=None, max_length=100, description="Version label")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {v}. Must be one of {VALID_STATUSES}")
        return v

    @field_validator("sub_anchor_type")
    @classmethod
    def validate_sub_anchor_type(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_SUB_ANCHOR_TYPES:
            raise ValueError(f"Invalid sub_anchor_type: {v}. Must be one of {VALID_SUB_ANCHOR_TYPES}")
        return v

    @model_validator(mode="after")
    def validate_payload(self) -> "EvidenceItemCreate":
        """Ensure exactly one payload field is set based on type."""
        if self.type == "file":
            if not self.asset_id:
                raise ValueError("asset_id is required for file type")
            if self.url or self.note_md:
                raise ValueError("url and note_md must be null for file type")
        elif self.type == "link":
            if not self.url:
                raise ValueError("url is required for link type")
            if self.asset_id or self.note_md:
                raise ValueError("asset_id and note_md must be null for link type")
        elif self.type == "note":
            if not self.note_md:
                raise ValueError("note_md is required for note type")
            if self.asset_id or self.url:
                raise ValueError("asset_id and url must be null for note type")
        return self


class EvidenceItemUpdate(BaseSchema):
    """Schema for updating evidence item."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    tags: list[str] | None = None
    source: str | None = None
    visibility: str | None = None
    url: str | None = Field(default=None, max_length=2000)
    note_md: str | None = Field(default=None, max_length=10000)
    locale: str | None = None
    # Workflow fields
    status: str | None = Field(default=None, description="Evidence status")
    sub_anchor_type: str | None = Field(default=None, description="table, chart, datapoint, or audit_check_item")
    sub_anchor_key: str | None = Field(default=None, max_length=255, description="Technical key for sub-anchor")
    sub_anchor_label: str | None = Field(default=None, max_length=255, description="Human-readable label")
    owner_user_id: UUID | None = Field(default=None, description="User responsible for this evidence")
    period_start: date | None = Field(default=None, description="Evidence period start date")
    period_end: date | None = Field(default=None, description="Evidence period end date")
    version_label: str | None = Field(default=None, max_length=100, description="Version label")

    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_VISIBILITY:
            raise ValueError(f"Invalid visibility: {v}. Must be one of {VALID_VISIBILITY}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {v}. Must be one of {VALID_STATUSES}")
        return v

    @field_validator("sub_anchor_type")
    @classmethod
    def validate_sub_anchor_type(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_SUB_ANCHOR_TYPES:
            raise ValueError(f"Invalid sub_anchor_type: {v}. Must be one of {VALID_SUB_ANCHOR_TYPES}")
        return v

    @field_validator("locale")
    @classmethod
    def validate_locale(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_LOCALES:
            raise ValueError(f"Invalid locale: {v}. Must be one of {VALID_LOCALES}")
        return v


class EvidenceItemDTO(EvidenceItemBase, TimestampSchema):
    """Evidence item data transfer object (response)."""

    evidence_id: UUID
    company_id: UUID
    asset_id: UUID | None = None
    url: str | None = None
    note_md: str | None = None
    created_by: UUID | None = None
    # Workflow fields
    status: str = Field(default="provided", description="Evidence status")
    sub_anchor_type: str | None = None
    sub_anchor_key: str | None = None
    sub_anchor_label: str | None = None
    owner_user_id: UUID | None = None
    period_start: date | None = None
    period_end: date | None = None
    version_label: str | None = None
    # Soft delete fields
    deleted_at: datetime | None = None
    deleted_by: UUID | None = None


class EvidenceItemWithAssetDTO(EvidenceItemDTO):
    """Evidence item with asset details (for file type)."""

    asset_filename: str | None = None
    asset_mime_type: str | None = None
    asset_size_bytes: int | None = None


# =============================================================================
# Query/Filter Schemas
# =============================================================================


class EvidenceFilter(BaseSchema):
    """Filter for querying evidence items."""

    scope_type: str | None = None
    scope_id: UUID | None = None
    type: str | None = None
    visibility: str | None = None
    tags: list[str] | None = None
    locale: str | None = None
    # Workflow filters
    status: str | None = None
    owner_user_id: UUID | None = None
    include_deleted: bool = False


# =============================================================================
# Summary Schemas
# =============================================================================


class EvidenceSummaryDTO(BaseSchema):
    """Summary of evidence for a scope."""

    scope_type: str
    scope_id: UUID
    total_count: int
    file_count: int
    link_count: int
    note_count: int
    by_visibility: dict[str, int]  # {"team": 5, "audit": 3}
    by_status: dict[str, int]  # {"provided": 3, "reviewed": 2}
