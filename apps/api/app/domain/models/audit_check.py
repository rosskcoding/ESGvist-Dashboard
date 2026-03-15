"""
AuditCheck model — Audit checklist items.

Auditors mark sections/blocks/evidence as reviewed, flagged, or needs_info.
Supports live review (no snapshot) and snapshot-based review.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin
from .enums import AuditCheckSeverity, AuditCheckStatus, AuditCheckTargetType

if TYPE_CHECKING:
    from .company import Company
    from .release import SourceSnapshot
    from .report import Report
    from .user import User


class AuditCheck(Base, TimestampMixin):
    """
    AuditCheck — auditor review status for content items.

    Target types:
    - report: overall report review
    - section: section-level review
    - block: block-level review
    - evidence_item: evidence review

    Status flow:
    - not_started -> in_review -> reviewed/flagged/needs_info

    Invariants:
    - source_snapshot_id NULL = live review (current content)
    - source_snapshot_id non-NULL = snapshot-based review
    - severity only set when status is flagged
    """

    __tablename__ = "audit_checks"

    check_id: Mapped[UUID] = mapped_column(
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
    source_snapshot_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("source_snapshots.snapshot_id", ondelete="SET NULL"),
        nullable=True,
        doc="NULL = live review, non-NULL = snapshot-based review",
    )
    # Target
    target_type: Mapped[AuditCheckTargetType] = mapped_column(
        SQLEnum(
            AuditCheckTargetType,
            name="audit_check_target_type_enum",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    target_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    # Auditor
    auditor_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=False,
        index=True,
    )
    # Status
    status: Mapped[AuditCheckStatus] = mapped_column(
        SQLEnum(
            AuditCheckStatus,
            name="audit_check_status_enum",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=AuditCheckStatus.NOT_STARTED,
    )
    severity: Mapped[AuditCheckSeverity | None] = mapped_column(
        SQLEnum(
            AuditCheckSeverity,
            name="audit_check_severity_enum",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
        doc="Severity of finding (only when flagged)",
    )
    comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    reviewed_at_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
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
    source_snapshot: Mapped["SourceSnapshot | None"] = relationship(
        "SourceSnapshot",
        foreign_keys=[source_snapshot_id],
    )
    auditor: Mapped["User"] = relationship(
        "User",
        foreign_keys=[auditor_id],
    )

    def __repr__(self) -> str:
        snapshot_str = f" snapshot={self.source_snapshot_id}" if self.source_snapshot_id else " [live]"
        return f"<AuditCheck {self.status.value} on {self.target_type.value}:{self.target_id}{snapshot_str}>"

    @property
    def is_live_review(self) -> bool:
        """Check if this is a live review (no snapshot)."""
        return self.source_snapshot_id is None

    @property
    def is_reviewed(self) -> bool:
        """Check if check is completed (reviewed, flagged, or needs_info)."""
        return self.status in (
            AuditCheckStatus.REVIEWED,
            AuditCheckStatus.FLAGGED,
            AuditCheckStatus.NEEDS_INFO,
        )

    @property
    def is_flagged(self) -> bool:
        return self.status == AuditCheckStatus.FLAGGED

    @property
    def is_critical(self) -> bool:
        """Check if flagged with critical severity."""
        return self.is_flagged and self.severity == AuditCheckSeverity.CRITICAL

    def mark_reviewed(self) -> None:
        """Mark as reviewed."""
        self.status = AuditCheckStatus.REVIEWED
        self.reviewed_at_utc = datetime.utcnow()

    def mark_flagged(self, severity: AuditCheckSeverity, comment: str | None = None) -> None:
        """Mark as flagged with severity."""
        self.status = AuditCheckStatus.FLAGGED
        self.severity = severity
        self.comment = comment
        self.reviewed_at_utc = datetime.utcnow()

    def mark_needs_info(self, comment: str | None = None) -> None:
        """Mark as needs more info."""
        self.status = AuditCheckStatus.NEEDS_INFO
        self.comment = comment
        self.reviewed_at_utc = datetime.utcnow()


