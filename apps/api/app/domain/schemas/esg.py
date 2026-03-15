"""
ESG Dashboard schemas (MVP).

Includes:
- Dimensions (entities/locations/segments)
- Metrics
- Facts (versioned values)
"""

from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import Field, model_validator

from .common import BaseSchema, TimestampSchema


class EsgMetricValueTypeEnum(str, Enum):
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    STRING = "string"
    DATASET = "dataset"


# =============================================================================
# Dimensions (Entity / Location / Segment)
# =============================================================================


class EsgDimensionBase(BaseSchema):
    code: str | None = Field(default=None, max_length=80)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    is_active: bool = True


class EsgEntityCreate(EsgDimensionBase):
    pass


class EsgEntityUpdate(BaseSchema):
    code: str | None = Field(default=None, max_length=80)
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    is_active: bool | None = None


class EsgEntityDTO(EsgDimensionBase, TimestampSchema):
    entity_id: UUID
    company_id: UUID
    created_by: UUID | None = None


class EsgLocationCreate(EsgDimensionBase):
    pass


class EsgLocationUpdate(BaseSchema):
    code: str | None = Field(default=None, max_length=80)
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    is_active: bool | None = None


class EsgLocationDTO(EsgDimensionBase, TimestampSchema):
    location_id: UUID
    company_id: UUID
    created_by: UUID | None = None


class EsgSegmentCreate(EsgDimensionBase):
    pass


class EsgSegmentUpdate(BaseSchema):
    code: str | None = Field(default=None, max_length=80)
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    is_active: bool | None = None


class EsgSegmentDTO(EsgDimensionBase, TimestampSchema):
    segment_id: UUID
    company_id: UUID
    created_by: UUID | None = None


# =============================================================================
# Metrics
# =============================================================================


class EsgMetricBase(BaseSchema):
    code: str | None = Field(default=None, max_length=80)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    value_type: EsgMetricValueTypeEnum
    unit: str | None = Field(default=None, max_length=64)
    value_schema_json: dict = Field(default_factory=dict)
    is_active: bool = True


class EsgMetricCreate(EsgMetricBase):
    pass


class EsgMetricUpdate(BaseSchema):
    code: str | None = Field(default=None, max_length=80)
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    value_type: EsgMetricValueTypeEnum | None = None
    unit: str | None = Field(default=None, max_length=64)
    value_schema_json: dict | None = None
    is_active: bool | None = None


class EsgMetricDTO(EsgMetricBase, TimestampSchema):
    metric_id: UUID
    company_id: UUID
    created_by: UUID | None = None
    updated_by: UUID | None = None


# =============================================================================
# Metric Assignments (Owners)
# =============================================================================


class EsgMetricOwnerUpsert(BaseSchema):
    owner_user_id: UUID | None = None


class EsgMetricOwnerDTO(BaseSchema):
    metric_id: UUID
    owner_user_id: UUID | None = None
    owner_user_name: str | None = None
    owner_user_email: str | None = None
    updated_at_utc: datetime | None = None


# =============================================================================
# Facts
# =============================================================================


class EsgFactStatusEnum(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"


class EsgPeriodTypeEnum(str, Enum):
    DAY = "day"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"
    CUSTOM = "custom"


class EsgFactBase(BaseSchema):
    metric_id: UUID

    # Period
    period_type: EsgPeriodTypeEnum
    period_start: date
    period_end: date
    is_ytd: bool = False

    # Context
    entity_id: UUID | None = None
    location_id: UUID | None = None
    segment_id: UUID | None = None
    consolidation_approach: str | None = None
    ghg_scope: str | None = None
    scope2_method: str | None = None
    scope3_category: str | None = None
    tags: list[str] | None = None

    # Value
    value_json: Any | None = None
    dataset_id: UUID | None = None

    quality_json: dict = Field(default_factory=dict)
    sources_json: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_period(self) -> "EsgFactBase":
        if self.period_start and self.period_end and self.period_start > self.period_end:
            raise ValueError("period_start must be <= period_end")
        return self

    @model_validator(mode="after")
    def _validate_value_presence(self) -> "EsgFactBase":
        # XOR check; type-specific validation happens server-side based on metric.value_type.
        if (self.value_json is None) == (self.dataset_id is None):
            raise ValueError("Exactly one of value_json or dataset_id must be provided")
        return self


class EsgFactCreate(EsgFactBase):
    pass


class EsgFactUpdate(BaseSchema):
    value_json: Any | None = None
    dataset_id: UUID | None = None
    quality_json: dict | None = None
    sources_json: dict | None = None

    @model_validator(mode="after")
    def _validate_patch(self) -> "EsgFactUpdate":
        if self.value_json is not None and self.dataset_id is not None:
            raise ValueError("Provide only one of value_json or dataset_id")
        return self


class EsgFactRequestChanges(BaseSchema):
    reason: str = Field(min_length=1, max_length=2000)


class EsgFactDTO(EsgFactBase, TimestampSchema):
    fact_id: UUID
    company_id: UUID
    status: EsgFactStatusEnum
    version_number: int
    supersedes_fact_id: UUID | None = None
    logical_key_hash: str

    # Populated by list endpoint; optional to avoid adding extra joins to all fact responses.
    evidence_count: int | None = None

    dataset_revision_id: UUID | None = None

    published_at_utc: datetime | None = None
    published_by: UUID | None = None
    created_by: UUID | None = None
    updated_by: UUID | None = None


# =============================================================================
# Fact Evidence
# =============================================================================


class EsgFactEvidenceTypeEnum(str, Enum):
    FILE = "file"
    LINK = "link"
    NOTE = "note"


class EsgFactEvidenceCreate(BaseSchema):
    type: EsgFactEvidenceTypeEnum
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None

    asset_id: UUID | None = None
    url: str | None = None
    note_md: str | None = None
    source: str | None = None
    source_date: date | None = None
    owner_user_id: UUID | None = None

    @model_validator(mode="after")
    def _validate_payload(self) -> "EsgFactEvidenceCreate":
        if self.type == EsgFactEvidenceTypeEnum.FILE:
            if self.asset_id is None or self.url is not None or self.note_md is not None:
                raise ValueError("File evidence requires asset_id and cannot include url/note_md")
        elif self.type == EsgFactEvidenceTypeEnum.LINK:
            if not self.url or self.asset_id is not None or self.note_md is not None:
                raise ValueError("Link evidence requires url and cannot include asset_id/note_md")
        elif self.type == EsgFactEvidenceTypeEnum.NOTE:
            if not self.note_md or self.asset_id is not None or self.url is not None:
                raise ValueError("Note evidence requires note_md and cannot include asset_id/url")
        return self


class EsgFactEvidenceDTO(TimestampSchema):
    evidence_id: UUID
    company_id: UUID
    fact_id: UUID
    type: EsgFactEvidenceTypeEnum
    title: str
    description: str | None = None
    asset_id: UUID | None = None
    url: str | None = None
    note_md: str | None = None
    source: str | None = None
    source_date: date | None = None
    owner_user_id: UUID | None = None
    created_by: UUID | None = None


class EsgFactEvidenceUpdate(BaseSchema):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    source: str | None = None
    source_date: date | None = None
    owner_user_id: UUID | None = None


# =============================================================================
# Compare
# =============================================================================


class EsgFactCompareRequest(BaseSchema):
    logical_key_hashes: list[str] = Field(min_length=1, max_length=200)


class EsgFactLatestDTO(BaseSchema):
    fact_id: UUID
    metric_id: UUID
    logical_key_hash: str
    version_number: int
    status: EsgFactStatusEnum
    dataset_id: UUID | None = None
    dataset_revision_id: UUID | None = None
    updated_at_utc: datetime
    published_at_utc: datetime | None = None


class EsgFactCompareItemDTO(BaseSchema):
    logical_key_hash: str
    latest: EsgFactLatestDTO | None = None
