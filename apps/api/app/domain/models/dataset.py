"""
Dataset and DatasetRevision models.

Dataset: Canonical data storage for tables and charts.
DatasetRevision: Snapshot/version history for release freezing.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .company import Company
    from .user import User


class Dataset(Base, TimestampMixin):
    """
    Dataset entity — canonical data storage.

    Stores tabular data that can be referenced by Table and Chart blocks.

    Invariants:
    - schema_json contains column definitions: [{key, type, unit?, nullable?}]
    - rows_json is array of arrays (not dict) for performance
    - current_revision increments on each data change
    - meta_json stores source attribution, period, currency, notes
    """

    __tablename__ = "datasets"

    dataset_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Tenant binding
    company_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.company_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Identity
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Human-readable name (e.g., 'Financial Metrics 2024')",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Optional description/context",
    )

    # Schema definition
    schema_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        doc="Column schema: {columns: [{key, type, unit?, format?, nullable?}]}",
    )

    # Current data
    rows_json: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        doc="Array of rows: [[val1, val2, ...], ...]",
    )

    # Metadata
    meta_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        doc="Source, period, currency, notes, etc.",
    )

    # Versioning
    current_revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        doc="Increments on each data change",
    )

    # Ownership
    created_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    # Soft delete
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="datasets")
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    updater: Mapped["User | None"] = relationship("User", foreign_keys=[updated_by])
    revisions: Mapped[list["DatasetRevision"]] = relationship(
        "DatasetRevision",
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="DatasetRevision.revision_number.desc()",
    )

    def __repr__(self) -> str:
        return f"<Dataset {self.dataset_id} '{self.name}' rev={self.current_revision}>"


class DatasetRevision(Base):
    """
    Dataset revision/snapshot.

    Created when:
    - User explicitly creates a snapshot
    - Release is built (auto-snapshot of all referenced datasets)

    Immutable after creation.
    """

    __tablename__ = "dataset_revisions"

    revision_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    dataset_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("datasets.dataset_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    revision_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Monotonic revision number (1, 2, 3, ...)",
    )

    # Snapshot of data at this revision
    schema_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        doc="Column schema snapshot",
    )
    rows_json: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        doc="Data snapshot",
    )
    meta_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        doc="Metadata snapshot",
    )

    # Attribution
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    reason: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Why this revision was created (e.g., 'Release 2024-Q1')",
    )

    # Relationships
    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="revisions")
    creator: Mapped["User | None"] = relationship("User")

    def __repr__(self) -> str:
        return f"<DatasetRevision {self.revision_id} dataset={self.dataset_id} rev={self.revision_number}>"

