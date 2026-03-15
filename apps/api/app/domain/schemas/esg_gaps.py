"""
ESG gaps / completeness schemas.

No new DB entities: computed on demand from existing metrics, facts, and evidence.
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import Field

from .common import BaseSchema
from .esg import EsgFactStatusEnum, EsgMetricValueTypeEnum, EsgPeriodTypeEnum


class EsgGapMetricDTO(BaseSchema):
    metric_id: UUID
    code: str | None = None
    name: str
    value_type: EsgMetricValueTypeEnum
    unit: str | None = None


class EsgGapIssueDTO(BaseSchema):
    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=2000)


class EsgGapFactAttentionDTO(BaseSchema):
    fact_id: UUID
    metric: EsgGapMetricDTO
    logical_key_hash: str = Field(min_length=64, max_length=64)
    status: EsgFactStatusEnum
    updated_at_utc: datetime
    issues: list[EsgGapIssueDTO] = Field(default_factory=list)


class EsgGapsDTO(BaseSchema):
    period_type: EsgPeriodTypeEnum
    period_start: date
    period_end: date
    is_ytd: bool = False
    standard: str | None = Field(default=None, max_length=32)

    metrics_total: int = Field(ge=0)
    metrics_with_published: int = Field(ge=0)
    metrics_missing_published: int = Field(ge=0)

    missing_metrics: list[EsgGapMetricDTO] = Field(default_factory=list)
    attention_facts: list[EsgGapFactAttentionDTO] = Field(default_factory=list)

    issue_counts: dict[str, int] = Field(default_factory=dict)
    in_review_overdue: int = Field(ge=0)
