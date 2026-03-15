"""
ESG snapshot schemas.

No new DB entities: snapshots are computed on demand from published facts.
"""

from datetime import date, datetime

from pydantic import Field

from .common import BaseSchema
from .esg import EsgFactDTO, EsgPeriodTypeEnum
from .esg_gaps import EsgGapMetricDTO


class EsgSnapshotFactDTO(BaseSchema):
    fact: EsgFactDTO
    metric: EsgGapMetricDTO


class EsgSnapshotDTO(BaseSchema):
    period_type: EsgPeriodTypeEnum
    period_start: date
    period_end: date
    is_ytd: bool = False
    standard: str | None = Field(default=None, max_length=32)

    generated_at_utc: datetime
    snapshot_hash: str = Field(min_length=64, max_length=64)

    metrics_total: int = Field(ge=0)
    facts_published: int = Field(ge=0)
    missing_metrics: list[EsgGapMetricDTO] = Field(default_factory=list)
    facts: list[EsgSnapshotFactDTO] = Field(default_factory=list)
