"""Add comment_threads and comments tables.

Revision ID: 20251231_0800
Revises: 20251231_0700
Create Date: 2024-12-31

Comment threads for audit support:
- comment_threads: discussion threads on report/section/block
- comments: individual messages in threads (append-only)
- supports internal comments (team-only)
- soft delete for comments
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20251231_0800"
down_revision: str = "20251231_0700"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create comment_threads and comments tables."""

    # 1. Create comment_threads table
    op.create_table(
        "comment_threads",
        sa.Column(
            "thread_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.company_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reports.report_id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Anchor: where this thread is attached
        sa.Column(
            "anchor_type",
            sa.String(20),
            nullable=False,
            comment="report, section, or block",
        ),
        sa.Column(
            "anchor_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="ID of report, section, or block",
        ),
        # Sub-anchor for granularity (table/chart/datapoint/audit_check_item)
        sa.Column(
            "sub_anchor_type",
            sa.String(50),
            nullable=True,
            comment="table, chart, datapoint, or audit_check_item",
        ),
        sa.Column(
            "sub_anchor_key",
            sa.String(255),
            nullable=True,
            comment="Technical key for sub-anchor",
        ),
        sa.Column(
            "sub_anchor_label",
            sa.String(255),
            nullable=True,
            comment="Human-readable label for sub-anchor",
        ),
        # Thread status
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="open",
            comment="open or resolved",
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "resolved_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "resolved_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Constraints
        sa.CheckConstraint(
            "anchor_type IN ('report', 'section', 'block')",
            name="ck_comment_threads_anchor_type",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'resolved')",
            name="ck_comment_threads_status",
        ),
    )

    # Indexes for comment_threads
    op.create_index(
        "ix_comment_threads_company",
        "comment_threads",
        ["company_id"],
    )
    op.create_index(
        "ix_comment_threads_report",
        "comment_threads",
        ["report_id"],
    )
    op.create_index(
        "ix_comment_threads_anchor",
        "comment_threads",
        ["anchor_type", "anchor_id"],
    )
    op.create_index(
        "ix_comment_threads_status",
        "comment_threads",
        ["status"],
    )

    # 2. Create comments table
    op.create_table(
        "comments",
        sa.Column(
            "comment_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "thread_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("comment_threads.thread_id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Denormalized company_id for tenant isolation
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.company_id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Author
        sa.Column(
            "author_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "author_role_snapshot",
            sa.String(50),
            nullable=True,
            comment="Role at creation time (auditor, editor, etc.)",
        ),
        # Content
        sa.Column(
            "body",
            sa.Text,
            nullable=False,
            comment="Comment text (markdown/plain)",
        ),
        sa.Column(
            "is_internal",
            sa.Boolean,
            nullable=False,
            server_default="false",
            comment="Team-only comment, hidden from auditors",
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # Soft delete (append-only, but can be deleted)
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "deleted_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # Indexes for comments
    op.create_index(
        "ix_comments_thread",
        "comments",
        ["thread_id", "created_at"],
    )
    op.create_index(
        "ix_comments_company",
        "comments",
        ["company_id"],
    )
    op.create_index(
        "ix_comments_deleted_at",
        "comments",
        ["deleted_at"],
    )


def downgrade() -> None:
    """Drop comment_threads and comments tables."""

    op.drop_table("comments")
    op.drop_table("comment_threads")


