"""
CommentThread and Comment models — Audit support comments.

Comment threads attached to report/section/block for audit discussions.
Supports internal comments (team-only) and soft delete (append-only).
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import LockScopeType, ThreadStatus

if TYPE_CHECKING:
    from .company import Company
    from .report import Report
    from .user import User


class CommentThread(Base):
    """
    CommentThread — discussion thread attached to report/section/block.

    Threads can be:
    - open: ongoing discussion
    - resolved: closed/answered

    Sub-anchor support for granular attachment (table/chart/datapoint/audit_check_item).
    """

    __tablename__ = "comment_threads"

    thread_id: Mapped[UUID] = mapped_column(
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
    # Anchor: where this thread is attached
    anchor_type: Mapped[LockScopeType] = mapped_column(
        SQLEnum(
            LockScopeType,
            name="comment_thread_anchor_type_enum",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    anchor_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        doc="ID of report, section, or block",
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
    # Thread status
    status: Mapped[ThreadStatus] = mapped_column(
        SQLEnum(
            ThreadStatus,
            name="thread_status_enum",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ThreadStatus.OPEN,
    )
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolved_by: Mapped[UUID | None] = mapped_column(
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
    creator: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[created_by],
    )
    resolver: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[resolved_by],
    )
    comments: Mapped[list["Comment"]] = relationship(
        "Comment",
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="Comment.created_at",
    )

    def __repr__(self) -> str:
        return f"<CommentThread {self.status.value} on {self.anchor_type.value}:{self.anchor_id}>"

    @property
    def is_open(self) -> bool:
        """Check if thread is open."""
        return self.status == ThreadStatus.OPEN

    @property
    def is_resolved(self) -> bool:
        """Check if thread is resolved."""
        return self.status == ThreadStatus.RESOLVED

    def resolve(self, resolved_by: UUID) -> None:
        """Mark thread as resolved."""
        self.status = ThreadStatus.RESOLVED
        self.resolved_at = datetime.now(UTC)
        self.resolved_by = resolved_by

    def reopen(self) -> None:
        """Reopen thread."""
        self.status = ThreadStatus.OPEN
        self.resolved_at = None
        self.resolved_by = None


class Comment(Base):
    """
    Comment — individual message in a comment thread.

    Append-only design:
    - No editing (create new comment instead)
    - Soft delete only (mark as deleted)
    - is_internal: team-only comments (hidden from auditors)

    Author role snapshot: stored at creation time for audit trail.
    """

    __tablename__ = "comments"

    comment_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    thread_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("comment_threads.thread_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Denormalized company_id for tenant isolation
    company_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.company_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Author
    author_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    author_role_snapshot: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Role at creation time (auditor, editor, etc.)",
    )
    # Content
    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Comment text (markdown/plain)",
    )
    is_internal: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Team-only comment, hidden from auditors",
    )
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    # Soft delete (append-only, but can be deleted)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deleted_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    thread: Mapped["CommentThread"] = relationship(
        "CommentThread",
        back_populates="comments",
        foreign_keys=[thread_id],
    )
    company: Mapped["Company"] = relationship(
        "Company",
        foreign_keys=[company_id],
    )
    author: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[author_user_id],
    )
    deleter: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[deleted_by],
    )

    def __repr__(self) -> str:
        deleted_str = " [deleted]" if self.is_deleted else ""
        internal_str = " [internal]" if self.is_internal else ""
        return f"<Comment {self.comment_id}{deleted_str}{internal_str}>"

    @property
    def is_deleted(self) -> bool:
        """Check if soft deleted."""
        return self.deleted_at is not None

    def soft_delete(self, deleted_by: UUID) -> None:
        """Mark comment as deleted."""
        self.deleted_at = datetime.now(UTC)
        self.deleted_by = deleted_by


