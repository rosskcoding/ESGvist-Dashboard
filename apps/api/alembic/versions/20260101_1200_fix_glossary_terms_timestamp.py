"""Add missing created_at_utc column to glossary_terms.

Revision ID: 20260101_1200
Revises: 20260101_1100
Create Date: 2026-01-01 12:00:00.000000

The glossary_terms table was created with only updated_at_utc, but the
GlossaryTerm model uses TimestampMixin which requires both created_at_utc
and updated_at_utc columns.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260101_1200"
down_revision = "20260101_1100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add missing created_at_utc column to glossary_terms.
    #
    # NOTE: This migration may be applied after a manual hotfix in some dev DBs.
    # Use IF NOT EXISTS to avoid failing if the column is already present.
    op.execute(
        "ALTER TABLE glossary_terms "
        "ADD COLUMN IF NOT EXISTS created_at_utc TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()"
    )


def downgrade() -> None:
    # Symmetric downgrade; keep it safe if the column is already removed.
    op.execute("ALTER TABLE glossary_terms DROP COLUMN IF EXISTS created_at_utc")

