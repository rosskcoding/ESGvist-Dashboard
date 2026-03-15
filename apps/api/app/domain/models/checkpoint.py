"""
ReportCheckpoint model — manual version snapshots for reports.

Provides:
- Manual checkpoint creation with optional comment
- Full report state snapshot (sections + blocks + i18n)
- Restore capability to any checkpoint
- Content hash for integrity and deduplication
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .company import Company
    from .report import Report
    from .user import User


class ReportCheckpoint(Base):
    """
    Manual checkpoint (version snapshot) for a report.

    Stores complete report state including:
    - Report metadata (title, year, locales)
    - All sections with i18n
    - All blocks with i18n

    Invariants:
    - snapshot_json follows content-snapshot.json format (from release builds)
    - content_root_hash = sha256(canonical_json(snapshot))
    - Max 30 checkpoints per report (enforced in service layer)
    - Max 100MB total storage per report (enforced in service layer)

    Lifecycle:
    - Created manually by Editor/ContentEditor
    - Never updated (immutable)
    - Auto-deleted when exceeding retention limits
    - Cascaded when report is deleted
    """

    __tablename__ = "report_checkpoints"

    checkpoint_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    report_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reports.report_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.company_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Denormalized for fast company-scoped queries",
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
        doc="User who created checkpoint (NULL if deleted)",
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Optional user comment (max 500 chars enforced in schema)",
    )
    content_root_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        doc="SHA256 hash of canonical snapshot for integrity/dedup",
    )
    snapshot_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        doc="Complete report snapshot (sections + blocks + i18n)",
    )
    snapshot_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        doc="Size of snapshot_json for storage quota enforcement",
    )

    # Relationships
    report: Mapped["Report"] = relationship(
        "Report",
        back_populates="checkpoints",
    )
    company: Mapped["Company"] = relationship(
        "Company",
        foreign_keys=[company_id],
    )
    creator: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[created_by],
    )

    def __repr__(self) -> str:
        comment_preview = self.comment[:30] if self.comment else "no comment"
        return f"<ReportCheckpoint {self.checkpoint_id} '{comment_preview}'>"


