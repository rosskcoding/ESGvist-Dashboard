"""Add evidence enhancements: status, sub_anchor, owner, soft delete.

Revision ID: 20251231_0700
Revises: 20251231_0600
Create Date: 2024-12-31

Adds workflow fields to evidence_items:
- status (provided/reviewed/issue/resolved)
- sub_anchor_* for granular anchoring (table/chart/datapoint)
- owner_user_id for assignment
- period_start/period_end for evidence time range
- version_label for tracking
- deleted_at/deleted_by for soft delete
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20251231_0700"
down_revision: str = "20251231_0600"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add evidence enhancement fields to evidence_items table."""

    # 1. Add status column
    op.add_column(
        "evidence_items",
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="provided",
            comment="provided, reviewed, issue, or resolved",
        ),
    )

    # 2. Add sub_anchor fields for granular anchoring
    op.add_column(
        "evidence_items",
        sa.Column(
            "sub_anchor_type",
            sa.String(50),
            nullable=True,
            comment="table, chart, datapoint, or audit_check_item",
        ),
    )
    op.add_column(
        "evidence_items",
        sa.Column(
            "sub_anchor_key",
            sa.String(255),
            nullable=True,
            comment="Technical key for sub-anchor",
        ),
    )
    op.add_column(
        "evidence_items",
        sa.Column(
            "sub_anchor_label",
            sa.String(255),
            nullable=True,
            comment="Human-readable label for sub-anchor",
        ),
    )

    # 3. Add owner_user_id for assignment
    op.add_column(
        "evidence_items",
        sa.Column(
            "owner_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
            nullable=True,
            comment="User responsible for this evidence",
        ),
    )

    # 4. Add period fields
    op.add_column(
        "evidence_items",
        sa.Column(
            "period_start",
            sa.Date,
            nullable=True,
            comment="Evidence period start date",
        ),
    )
    op.add_column(
        "evidence_items",
        sa.Column(
            "period_end",
            sa.Date,
            nullable=True,
            comment="Evidence period end date",
        ),
    )

    # 5. Add version_label
    op.add_column(
        "evidence_items",
        sa.Column(
            "version_label",
            sa.String(100),
            nullable=True,
            comment="Version label (e.g. 'ERP export v2')",
        ),
    )

    # 6. Add soft delete fields
    op.add_column(
        "evidence_items",
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "evidence_items",
        sa.Column(
            "deleted_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # 7. Add check constraint for status
    op.create_check_constraint(
        "ck_evidence_items_status",
        "evidence_items",
        "status IN ('provided', 'reviewed', 'issue', 'resolved')",
    )

    # 8. Add index on status for filtering
    op.create_index(
        "ix_evidence_items_status",
        "evidence_items",
        ["status"],
    )

    # 9. Add index on deleted_at for soft delete queries
    op.create_index(
        "ix_evidence_items_deleted_at",
        "evidence_items",
        ["deleted_at"],
    )


def downgrade() -> None:
    """Remove evidence enhancement fields."""

    op.drop_index("ix_evidence_items_deleted_at", "evidence_items")
    op.drop_index("ix_evidence_items_status", "evidence_items")
    op.drop_constraint("ck_evidence_items_status", "evidence_items", type_="check")

    op.drop_column("evidence_items", "deleted_by")
    op.drop_column("evidence_items", "deleted_at")
    op.drop_column("evidence_items", "version_label")
    op.drop_column("evidence_items", "period_end")
    op.drop_column("evidence_items", "period_start")
    op.drop_column("evidence_items", "owner_user_id")
    op.drop_column("evidence_items", "sub_anchor_label")
    op.drop_column("evidence_items", "sub_anchor_key")
    op.drop_column("evidence_items", "sub_anchor_type")
    op.drop_column("evidence_items", "status")


