"""
ESG Fact model for ESG Dashboard pillar.

Facts are company-scoped and versioned by a logical key hash + version_number.

Table/time-series values are stored in the existing `datasets` tables.
Scalar values are stored in `value_json`.
"""

from __future__ import annotations

from datetime import datetime, date
from enum import Enum
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class EsgFactStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"


class EsgFact(Base, TimestampMixin):
    __tablename__ = "esg_facts"
    __table_args__ = (
        # Version uniqueness within tenant + logical key group.
        UniqueConstraint(
            "company_id",
            "logical_key_hash",
            "version_number",
            name="uq_esg_facts_company_logical_version",
        ),
        # Exactly one published per logical key per company.
        Index(
            "uq_esg_facts_company_published_logical_key",
            "company_id",
            "logical_key_hash",
            unique=True,
            postgresql_where=sa.text("status = 'published'"),
        ),
        # One of (value_json, dataset_id) must be set (but not both).
        CheckConstraint(
            "(value_json IS NOT NULL AND dataset_id IS NULL) OR (value_json IS NULL AND dataset_id IS NOT NULL)",
            name="ck_esg_facts_value_xor_dataset",
        ),
        # Scalar facts cannot have dataset_revision_id.
        CheckConstraint(
            "(value_json IS NULL) OR (dataset_revision_id IS NULL)",
            name="ck_esg_facts_scalar_no_dataset_revision",
        ),
        # Period sanity.
        CheckConstraint("period_start <= period_end", name="ck_esg_facts_period_range"),
        # Filter indexes (company-scoped).
        Index("ix_esg_facts_company_metric", "company_id", "metric_id"),
        Index("ix_esg_facts_company_logical_key", "company_id", "logical_key_hash"),
        Index("ix_esg_facts_company_entity", "company_id", "entity_id"),
        Index("ix_esg_facts_company_location", "company_id", "location_id"),
        Index("ix_esg_facts_company_segment", "company_id", "segment_id"),
        Index("ix_esg_facts_company_period_start", "company_id", "period_start"),
        Index("ix_esg_facts_company_period_end", "company_id", "period_end"),
    )

    fact_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    company_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.company_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    metric_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("esg_metrics.metric_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[EsgFactStatus] = mapped_column(
        SQLEnum(
            EsgFactStatus,
            name="esg_fact_status_enum",
            length=32,  # prevent truncation when adding longer status values
            native_enum=False,
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=EsgFactStatus.DRAFT,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    supersedes_fact_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("esg_facts.fact_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    logical_key_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Period
    period_type: Mapped[str] = mapped_column(String(16), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    is_ytd: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Context
    entity_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("esg_entities.entity_id", ondelete="SET NULL"),
        nullable=True,
    )
    location_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("esg_locations.location_id", ondelete="SET NULL"),
        nullable=True,
    )
    segment_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("esg_segments.segment_id", ondelete="SET NULL"),
        nullable=True,
    )
    consolidation_approach: Mapped[str | None] = mapped_column(Text, nullable=True)
    ghg_scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope2_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope3_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String(100)), nullable=True)

    # Value
    # NOTE: We need SQL NULL semantics for versioning constraints (XOR with dataset_id).
    # JSONB by default stores Python None as JSON null; `none_as_null=True` ensures SQL NULL.
    value_json: Mapped[object | None] = mapped_column(JSONB(none_as_null=True), nullable=True)
    dataset_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("datasets.dataset_id", ondelete="SET NULL"),
        nullable=True,
    )
    dataset_revision_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("dataset_revisions.revision_id", ondelete="SET NULL"),
        nullable=True,
    )

    # Additional metadata
    quality_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    sources_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    published_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    created_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    company = relationship("Company")
    metric = relationship("EsgMetric")
    supersedes = relationship("EsgFact", remote_side="EsgFact.fact_id")

    def __repr__(self) -> str:
        return (
            f"<EsgFact {self.fact_id} metric={self.metric_id} "
            f"status={self.status.value} v={self.version_number} key={self.logical_key_hash[:8]}...>"
        )
