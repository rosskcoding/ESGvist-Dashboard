"""Add content_locks table.

Revision ID: 20241227_0004
Revises: 20241227_0003
Create Date: 2024-12-27

Two-layer content locks: coord (coordinator) and audit layers.
Audit lock is stronger than coord lock.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20241227_0004"
down_revision: str = "20241227_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create content_locks table."""

    op.create_table(
        "content_locks",
        sa.Column(
            "lock_id",
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
            "scope_type",
            sa.String(20),
            nullable=False,
            comment="report, section, or block",
        ),
        sa.Column(
            "scope_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="ID of report, section, or block",
        ),
        sa.Column(
            "lock_layer",
            sa.String(10),
            nullable=False,
            comment="coord or audit - audit is stronger",
        ),
        sa.Column(
            "is_locked",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "reason",
            sa.Text,
            nullable=False,
        ),
        sa.Column(
            "locked_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
            nullable=False,
        ),
        sa.Column(
            "locked_at_utc",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "released_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "released_at_utc",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "updated_at_utc",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "scope_type IN ('report', 'section', 'block')",
            name="ck_content_locks_scope_type",
        ),
        sa.CheckConstraint(
            "lock_layer IN ('coord', 'audit')",
            name="ck_content_locks_layer",
        ),
    )

    # Partial unique index: only one active lock per (scope_type, scope_id, lock_layer)
    op.create_index(
        "ux_content_locks_active",
        "content_locks",
        ["scope_type", "scope_id", "lock_layer"],
        unique=True,
        postgresql_where=sa.text("is_locked = true"),
    )

    # Index for scope lookups
    op.create_index(
        "ix_content_locks_scope",
        "content_locks",
        ["scope_type", "scope_id"],
    )

    # Index for company lookups
    op.create_index(
        "ix_content_locks_company",
        "content_locks",
        ["company_id"],
    )


def downgrade() -> None:
    """Drop content_locks table."""
    op.drop_table("content_locks")


