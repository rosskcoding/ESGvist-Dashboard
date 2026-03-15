"""Extend locale enum with additional languages.

Revision ID: 20260215_1100
Revises: 20260215_0900
Create Date: 2026-02-15 11:00:00
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260215_1100"
down_revision: str | Sequence[str] | None = "20260215_0900"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # NOTE:
    # - ALTER TYPE ... ADD VALUE cannot run inside a transaction in some Postgres setups.
    # - Alembic env uses begin_transaction(), so we must use autocommit_block().
    with op.get_context().autocommit_block():
        op.execute(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'locale') THEN
                    ALTER TYPE locale ADD VALUE IF NOT EXISTS 'de';
                    ALTER TYPE locale ADD VALUE IF NOT EXISTS 'fr';
                    ALTER TYPE locale ADD VALUE IF NOT EXISTS 'ar';
                    ALTER TYPE locale ADD VALUE IF NOT EXISTS 'es';
                    ALTER TYPE locale ADD VALUE IF NOT EXISTS 'nl';
                    ALTER TYPE locale ADD VALUE IF NOT EXISTS 'it';
                END IF;
            END $$;
            """
        )


def downgrade() -> None:
    # PostgreSQL doesn't support removing enum values directly.
    pass

