"""Extend ESG fact status lifecycle.

Revision ID: 20260214_1600
Revises: 20260214_1500
Create Date: 2026-02-14 16:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260214_1600"
down_revision: str | Sequence[str] | None = "20260214_1500"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _drop_old_status_check_constraints(*, allowed_values: list[str]) -> None:
    """
    Drop any existing CHECK constraint that enforces esg_facts.status allowed values.

    The original table was created with a SQLAlchemy Enum CHECK constraint, but the
    constraint name may vary between environments (migrations vs create_all in tests).
    """
    bind = op.get_bind()
    values_sql = " AND ".join([f"pg_get_constraintdef(c.oid) ILIKE '%{v}%'" for v in allowed_values])
    rows = bind.execute(
        sa.text(
            f"""
            SELECT c.conname
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE n.nspname = current_schema()
              AND t.relname = 'esg_facts'
              AND c.contype = 'c'
              AND pg_get_constraintdef(c.oid) ILIKE '%status%'
              AND pg_get_constraintdef(c.oid) ILIKE '%IN%'
              AND {values_sql}
            """
        )
    ).fetchall()

    for (name,) in rows:
        op.drop_constraint(name, "esg_facts", type_="check")


def upgrade() -> None:
    _drop_old_status_check_constraints(allowed_values=["draft", "published"])
    op.create_check_constraint(
        "esg_fact_status_enum",
        "esg_facts",
        "status IN ('draft', 'in_review', 'published', 'superseded')",
    )


def downgrade() -> None:
    _drop_old_status_check_constraints(allowed_values=["draft", "in_review", "published", "superseded"])
    op.create_check_constraint(
        "esg_fact_status_enum",
        "esg_facts",
        "status IN ('draft', 'published')",
    )

