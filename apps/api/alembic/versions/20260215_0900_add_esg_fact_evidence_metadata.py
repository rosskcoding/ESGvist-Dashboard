"""Add ESG fact evidence metadata fields.

Revision ID: 20260215_0900
Revises: 20260214_1700
Create Date: 2026-02-15 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260215_0900"
down_revision: str | Sequence[str] | None = "20260214_1700"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    def _column_exists(table: str, column: str) -> bool:
        return (
            bind.execute(
                sa.text(
                    """
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = :table
                      AND column_name = :column
                    LIMIT 1
                    """
                ),
                {"table": table, "column": column},
            ).scalar()
            is not None
        )

    if not _column_exists("esg_fact_evidence_items", "source"):
        op.add_column("esg_fact_evidence_items", sa.Column("source", sa.Text(), nullable=True))

    if not _column_exists("esg_fact_evidence_items", "source_date"):
        op.add_column("esg_fact_evidence_items", sa.Column("source_date", sa.Date(), nullable=True))

    if not _column_exists("esg_fact_evidence_items", "owner_user_id"):
        op.add_column(
            "esg_fact_evidence_items",
            sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.create_foreign_key(
            "fk_esg_fact_evidence_owner_user_id",
            "esg_fact_evidence_items",
            "users",
            ["owner_user_id"],
            ["user_id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()

    def _column_exists(table: str, column: str) -> bool:
        return (
            bind.execute(
                sa.text(
                    """
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = :table
                      AND column_name = :column
                    LIMIT 1
                    """
                ),
                {"table": table, "column": column},
            ).scalar()
            is not None
        )

    def _constraint_exists(table: str, name: str) -> bool:
        return (
            bind.execute(
                sa.text(
                    """
                    SELECT 1
                    FROM information_schema.table_constraints
                    WHERE table_schema = current_schema()
                      AND table_name = :table
                      AND constraint_name = :name
                    LIMIT 1
                    """
                ),
                {"table": table, "name": name},
            ).scalar()
            is not None
        )

    if _constraint_exists("esg_fact_evidence_items", "fk_esg_fact_evidence_owner_user_id"):
        op.drop_constraint(
            "fk_esg_fact_evidence_owner_user_id",
            "esg_fact_evidence_items",
            type_="foreignkey",
        )

    if _column_exists("esg_fact_evidence_items", "owner_user_id"):
        op.drop_column("esg_fact_evidence_items", "owner_user_id")
    if _column_exists("esg_fact_evidence_items", "source_date"):
        op.drop_column("esg_fact_evidence_items", "source_date")
    if _column_exists("esg_fact_evidence_items", "source"):
        op.drop_column("esg_fact_evidence_items", "source")

