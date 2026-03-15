"""Rename dataset timestamp columns to match TimestampMixin convention

Revision ID: 20251231_0500
Revises: 20251231_0400
Create Date: 2025-12-31 05:00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '20251231_0500'
down_revision = '20251231_0400'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Rename timestamp column in dataset_revisions table
    to match the TimestampMixin convention (_utc suffix).

    Note: datasets table already has correct column names (created_at_utc, updated_at_utc).
    """
    # Rename dataset_revisions column only
    op.alter_column('dataset_revisions', 'created_at', new_column_name='created_at_utc')


def downgrade() -> None:
    """
    Revert timestamp column name.
    """
    # Revert dataset_revisions column
    op.alter_column('dataset_revisions', 'created_at_utc', new_column_name='created_at')

