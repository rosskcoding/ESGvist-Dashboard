"""Add ESG metric assignments (owners).

Revision ID: 20260215_1800
Revises: 20260215_1100
Create Date: 2026-02-15 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260215_1800"
down_revision: str | Sequence[str] | None = "20260215_1100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    def _table_exists(table: str) -> bool:
        return (
            bind.execute(
                sa.text(
                    """
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = current_schema()
                      AND table_name = :table
                    LIMIT 1
                    """
                ),
                {"table": table},
            ).scalar()
            is not None
        )

    if _table_exists("esg_metric_assignments"):
        return

    op.create_table(
        "esg_metric_assignments",
        sa.Column("assignment_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.company_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "metric_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("esg_metrics.metric_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "owner_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at_utc",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("company_id", "metric_id", name="uq_esg_metric_assignments_company_metric"),
    )

    op.create_index("ix_esg_metric_assignments_company_id", "esg_metric_assignments", ["company_id"])
    op.create_index("ix_esg_metric_assignments_metric_id", "esg_metric_assignments", ["metric_id"])
    op.create_index("ix_esg_metric_assignments_owner_user_id", "esg_metric_assignments", ["owner_user_id"])


def downgrade() -> None:
    bind = op.get_bind()

    def _table_exists(table: str) -> bool:
        return (
            bind.execute(
                sa.text(
                    """
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = current_schema()
                      AND table_name = :table
                    LIMIT 1
                    """
                ),
                {"table": table},
            ).scalar()
            is not None
        )

    if not _table_exists("esg_metric_assignments"):
        return

    for idx in [
        "ix_esg_metric_assignments_owner_user_id",
        "ix_esg_metric_assignments_metric_id",
        "ix_esg_metric_assignments_company_id",
    ]:
        op.drop_index(idx, table_name="esg_metric_assignments")

    op.drop_table("esg_metric_assignments")

