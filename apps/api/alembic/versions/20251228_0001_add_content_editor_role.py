"""Add content_editor and corporate_lead roles to assignable_role enum.

Revision ID: 20251228_0001
Revises: 20251227_0001
Create Date: 2025-12-28

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20251228_0001"
down_revision: Union[str, None] = "20251227_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Legacy compatibility:
    # In older schema revisions roles were stored in Postgres enum assignable_role_enum.
    # In current schema role_assignments.role is VARCHAR + CHECK constraint, so this step is a no-op.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'assignable_role_enum') THEN
                ALTER TYPE assignable_role_enum ADD VALUE IF NOT EXISTS 'content_editor';
                ALTER TYPE assignable_role_enum ADD VALUE IF NOT EXISTS 'corporate_lead';
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # PostgreSQL doesn't support removing enum values directly
    # This would require recreating the enum type
    pass
