"""
EvidenceItem model — Evidence storage for audit.

Supports file, link, and note types attached to report/section/block.
Visibility controls who can see evidence (team vs auditors).

Enhanced workflow fields (see migrations / tests):
- status (provided/reviewed/issue/resolved)
- sub_anchor_* for granular anchoring (table/chart/datapoint/audit_check_item)
- owner_user_id for assignment
- period_start/period_end for evidence time range
- version_label for tracking
- deleted_at/deleted_by for soft delete
"""

from datetime import UTC, datetime, date
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, Date
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin
from .enums import EvidenceSource, EvidenceStatus, EvidenceType, EvidenceVisibility, LockScopeType

if TYPE_CHECKING:
    from .asset import Asset
    from .company import Company
    from .report import Report
    from .user import User


class EvidenceItem(Base, TimestampMixin):
    """
    EvidenceItem — audit evidence attached to report/section/block.

    Types:
    - file: references an Asset
    - link: external URL
    - note: markdown text

    Visibility:
    - team: visible to company team (editor, reviewer, etc.)
    - audit: visible to auditors in scope
    - restricted: limited access (future)

    Invariants:
    - Exactly one of asset_id, url, note_md must be set based on type
    - scope_type/scope_id defines attachment point
    """

    __tablename__ = "evidence_items"

    evidence_id: Mapped[UUID] = mapped_column(
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
    report_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reports.report_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Scoped attachment
    scope_type: Mapped[LockScopeType] = mapped_column(
        SQLEnum(
            LockScopeType,
            name="evidence_scope_type_enum",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    scope_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        doc="ID of report, section, or block",
    )
    # Evidence workflow status
    status: Mapped[EvidenceStatus] = mapped_column(
        SQLEnum(
            EvidenceStatus,
            name="evidence_status",
            native_enum=False,
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=EvidenceStatus.PROVIDED,
        server_default=EvidenceStatus.PROVIDED.value,
        doc="Evidence status: provided, reviewed, issue, resolved",
    )
    # Sub-anchor for granularity (table/chart/datapoint/audit_check_item)
    sub_anchor_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="table, chart, datapoint, or audit_check_item",
    )
    sub_anchor_key: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Technical key for sub-anchor",
    )
    sub_anchor_label: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Human-readable label for sub-anchor",
    )
    # Assignment / metadata
    owner_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
        doc="User responsible for this evidence",
    )
    period_start: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        doc="Evidence period start date",
    )
    period_end: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        doc="Evidence period end date",
    )
    version_label: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Version label (e.g. 'ERP export v2')",
    )
    # Soft delete
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deleted_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    locale: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )
    # Evidence type
    type: Mapped[EvidenceType] = mapped_column(
        SQLEnum(
            EvidenceType,
            name="evidence_type_enum",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    tags: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    source: Mapped[EvidenceSource | None] = mapped_column(
        SQLEnum(
            EvidenceSource,
            name="evidence_source_enum",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
    )
    visibility: Mapped[EvidenceVisibility] = mapped_column(
        SQLEnum(
            EvidenceVisibility,
            name="evidence_visibility_enum",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=EvidenceVisibility.TEAM,
    )
    # Type-specific payloads (mutually exclusive)
    asset_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("assets.asset_id", ondelete="SET NULL"),
        nullable=True,
    )
    url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    note_md: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    company: Mapped["Company"] = relationship(
        "Company",
        foreign_keys=[company_id],
    )
    report: Mapped["Report"] = relationship(
        "Report",
        foreign_keys=[report_id],
    )
    asset: Mapped["Asset | None"] = relationship(
        "Asset",
        foreign_keys=[asset_id],
    )
    creator: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[created_by],
    )

    def __repr__(self) -> str:
        return f"<EvidenceItem {self.type.value}: {self.title} ({self.evidence_id})>"

    @property
    def is_file(self) -> bool:
        return self.type == EvidenceType.FILE

    @property
    def is_link(self) -> bool:
        return self.type == EvidenceType.LINK

    @property
    def is_note(self) -> bool:
        return self.type == EvidenceType.NOTE

    @property
    def is_visible_to_team(self) -> bool:
        """Check if visible to team members."""
        return self.visibility in (EvidenceVisibility.TEAM, EvidenceVisibility.AUDIT)

    @property
    def is_visible_to_auditors(self) -> bool:
        """Check if visible to auditors."""
        return self.visibility == EvidenceVisibility.AUDIT

    @property
    def is_deleted(self) -> bool:
        """Soft delete flag (derived)."""
        return self.deleted_at is not None

    def soft_delete(self, deleted_by: UUID) -> None:
        """Soft delete this evidence item (append-only semantics)."""
        self.deleted_at = datetime.now(UTC)
        self.deleted_by = deleted_by

