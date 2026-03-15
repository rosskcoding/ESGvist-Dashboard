"""Add report_checkpoints table for version control

Revision ID: 20251231_0600
Revises: 20251231_0500
Create Date: 2025-12-31 06:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251231_0600'
down_revision = '20251231_0500'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create report_checkpoints table for manual version snapshots.

    Features:
    - Stores complete report state (sections + blocks + i18n)
    - Max 30 checkpoints per report (enforced in application)
    - 100MB total storage cap per report (enforced in application)
    - Content hash for deduplication and integrity checks
    """
    op.create_table(
        'report_checkpoints',
        sa.Column('checkpoint_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('report_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at_utc', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('content_root_hash', sa.String(64), nullable=False),
        sa.Column('snapshot_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('snapshot_size_bytes', sa.BigInteger(), nullable=False),

        # Foreign keys
        sa.ForeignKeyConstraint(['report_id'], ['reports.report_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.company_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.user_id'], ondelete='SET NULL'),

        # Indexes
        sa.PrimaryKeyConstraint('checkpoint_id'),
    )

    # Index for listing checkpoints by report (most common query)
    op.create_index(
        'ix_report_checkpoints_report_id_created_at',
        'report_checkpoints',
        ['report_id', 'created_at_utc'],
        unique=False
    )

    # Index for company-scoped queries (audit/admin)
    op.create_index(
        'ix_report_checkpoints_company_id',
        'report_checkpoints',
        ['company_id'],
        unique=False
    )

    # Index for hash-based deduplication checks
    op.create_index(
        'ix_report_checkpoints_content_hash',
        'report_checkpoints',
        ['content_root_hash'],
        unique=False
    )


def downgrade() -> None:
    """
    Drop report_checkpoints table and all indexes.
    """
    op.drop_index('ix_report_checkpoints_content_hash', table_name='report_checkpoints')
    op.drop_index('ix_report_checkpoints_company_id', table_name='report_checkpoints')
    op.drop_index('ix_report_checkpoints_report_id_created_at', table_name='report_checkpoints')
    op.drop_table('report_checkpoints')


