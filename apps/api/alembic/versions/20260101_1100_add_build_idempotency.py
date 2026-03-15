"""add build idempotency fields

Revision ID: 20260101_1100
Revises: 20251231_1000
Create Date: 2026-01-01 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260101_1100'
down_revision: Union[str, None] = '20251231_1000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add idempotency fields to release_builds table."""
    # Add idempotency_key (nullable, will be populated for new builds)
    op.add_column('release_builds', sa.Column('idempotency_key', sa.String(length=64), nullable=True))
    op.create_index(op.f('ix_release_builds_idempotency_key'), 'release_builds', ['idempotency_key'], unique=False)

    # Add retry tracking fields
    op.add_column('release_builds', sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('release_builds', sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'))


def downgrade() -> None:
    """Remove idempotency fields from release_builds table."""
    op.drop_index(op.f('ix_release_builds_idempotency_key'), table_name='release_builds')
    op.drop_column('release_builds', 'max_retries')
    op.drop_column('release_builds', 'retry_count')
    op.drop_column('release_builds', 'idempotency_key')


