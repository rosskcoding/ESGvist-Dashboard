"""Widen esg_facts.status column to support longer workflow states.

Revision ID: 20260214_1610
Revises: 20260214_1600
Create Date: 2026-02-14 16:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260214_1610"
down_revision: str | Sequence[str] | None = "20260214_1600"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Original non-native enum used VARCHAR(9) (max len of "published").
    op.alter_column(
        "esg_facts",
        "status",
        existing_type=sa.String(length=9),
        type_=sa.String(length=32),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Best-effort coercion so shrinking won't fail.
    op.execute("UPDATE esg_facts SET status = 'draft' WHERE status IN ('superseded')")
    op.alter_column(
        "esg_facts",
        "status",
        existing_type=sa.String(length=32),
        type_=sa.String(length=9),
        existing_nullable=False,
    )

