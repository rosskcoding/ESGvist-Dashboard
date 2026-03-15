"""
ContentVersion model — Lightweight change tracking for block content.

Stores last 3 versions of block content per locale.
Transactional retention (no cron needed).
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .block import Block
    from .company import Company
    from .report import Report
    from .user import User


class ContentVersion(Base):
    """
    ContentVersion — snapshot of block content at a point in time.

    Retention policy:
    - Keep max 3 versions per (block_id, locale)
    - Enforced transactionally on insert
    - No cron needed

    Triggered on BlockI18n.fields_json updates.
    """

    __tablename__ = "content_versions"

    version_id: Mapped[UUID] = mapped_column(
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
    block_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("blocks.block_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    locale: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        doc="Locale of the content version",
    )
    saved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    saved_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    fields_json_snapshot: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        doc="Snapshot of BlockI18n.fields_json at this point",
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
    block: Mapped["Block"] = relationship(
        "Block",
        foreign_keys=[block_id],
    )
    saver: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[saved_by],
    )

    def __repr__(self) -> str:
        return f"<ContentVersion {self.block_id}:{self.locale} at {self.saved_at}>"


