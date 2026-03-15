"""Fix esg_facts.status CHECK constraints for review lifecycle.

Revision ID: 20260214_1620
Revises: 20260214_1610
Create Date: 2026-02-14 16:20:00

Some environments may have an auto-generated CHECK constraint name for the
non-native enum (e.g. created via metadata.create_all). This migration drops
any legacy constraints that only allow ('draft','published') and replaces them
with a single canonical constraint allowing the full lifecycle.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260214_1620"
down_revision: str | Sequence[str] | None = "20260214_1610"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT c.conname, pg_get_constraintdef(c.oid) AS defn
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE n.nspname = current_schema()
              AND t.relname = 'esg_facts'
              AND c.contype = 'c'
              AND pg_get_constraintdef(c.oid) ILIKE '%status%'
            """
        )
    ).fetchall()

    for name, defn in rows:
        d = (defn or "").lower()
        # Legacy constraints that only allow the pre-review values.
        if "draft" in d and "published" in d and "in_review" not in d and "superseded" not in d:
            op.drop_constraint(name, "esg_facts", type_="check")

    op.execute("ALTER TABLE esg_facts DROP CONSTRAINT IF EXISTS esg_fact_status_enum")
    op.create_check_constraint(
        "esg_fact_status_enum",
        "esg_facts",
        "status IN ('draft', 'in_review', 'published', 'superseded')",
    )


def downgrade() -> None:
    op.execute("UPDATE esg_facts SET status = 'draft' WHERE status IN ('in_review', 'superseded')")
    op.execute("ALTER TABLE esg_facts DROP CONSTRAINT IF EXISTS esg_fact_status_enum")
    op.create_check_constraint(
        "esg_fact_status_enum",
        "esg_facts",
        "status IN ('draft', 'published')",
    )

