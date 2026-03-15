"""
ContentLock model — Two-layer content locking.

Supports coord (coordinator) and audit lock layers.
Audit lock is stronger than coord lock.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base
from .enums import LockLayer, LockScopeType

if TYPE_CHECKING:
    from .company import Company
    from .user import User


class ContentLock(Base):
    """
    ContentLock — hierarchical content locking with two layers.

    Lock hierarchy:
    - Lock on report -> blocks all sections and blocks
    - Lock on section -> blocks all blocks in section
    - Lock on block -> blocks specific block

    Lock layers:
    - coord: Coordinator/internal lock (can be released by lock:coord:release)
    - audit: Auditor lock (stronger, requires lock:audit:release or override)

    Invariants:
    - Only one active lock per (scope_type, scope_id, lock_layer)
    - Audit lock takes precedence over coord lock
    - reason is required for all locks
    """

    __tablename__ = "content_locks"

    lock_id: Mapped[UUID] = mapped_column(
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
    scope_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Scope type: report, section, block (stored as VARCHAR with CHECK constraint)",
    )
    scope_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        doc="ID of report, section, or block",
    )
    lock_layer: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        doc="Lock layer: coord, audit (stored as VARCHAR with CHECK constraint)",
    )
    is_locked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    locked_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=False,
    )
    locked_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    released_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    released_at_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    company: Mapped["Company"] = relationship(
        "Company",
        foreign_keys=[company_id],
    )
    locker: Mapped["User"] = relationship(
        "User",
        foreign_keys=[locked_by],
    )
    releaser: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[released_by],
    )

    def __repr__(self) -> str:
        status = "LOCKED" if self.is_locked else "released"
        return f"<ContentLock {self.lock_layer} on {self.scope_type}:{self.scope_id} [{status}]>"

    def release(self, released_by: UUID) -> None:
        """Mark lock as released."""
        self.is_locked = False
        self.released_by = released_by
        self.released_at_utc = datetime.utcnow()

    @property
    def is_audit_lock(self) -> bool:
        """Check if this is an audit-layer lock (stronger)."""
        return self.lock_layer == LockLayer.AUDIT.value

    @property
    def is_coord_lock(self) -> bool:
        """Check if this is a coordinator-layer lock."""
        return self.lock_layer == LockLayer.COORD.value

