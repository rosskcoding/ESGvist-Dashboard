"""Add dataset and dataset_revision tables

Revision ID: 20251231_0400
Revises: 20251231_0300
Create Date: 2025-12-31 04:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251231_0400'
down_revision = '20251231_0300'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add Dataset and DatasetRevision tables.

    Dataset: Canonical tabular data storage for tables/charts.
    DatasetRevision: Immutable snapshots for release freezing.
    """
    # Create datasets table
    op.create_table(
        'datasets',
        sa.Column('dataset_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('schema_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('rows_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('meta_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('current_revision', sa.Integer(), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.company_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.user_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['updated_by'], ['users.user_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('dataset_id')
    )

    # Indexes for datasets
    op.create_index(op.f('ix_datasets_company_id'), 'datasets', ['company_id'], unique=False)
    op.create_index('ix_datasets_company_not_deleted', 'datasets', ['company_id', 'is_deleted'], unique=False)

    # Create dataset_revisions table
    op.create_table(
        'dataset_revisions',
        sa.Column('revision_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('dataset_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('revision_number', sa.Integer(), nullable=False),
        sa.Column('schema_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('rows_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('meta_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reason', sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(['dataset_id'], ['datasets.dataset_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.user_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('revision_id')
    )

    # Indexes for dataset_revisions
    op.create_index(op.f('ix_dataset_revisions_dataset_id'), 'dataset_revisions', ['dataset_id'], unique=False)
    op.create_index('ix_dataset_revisions_dataset_revision', 'dataset_revisions', ['dataset_id', 'revision_number'], unique=True)

    # Add dataset_id to blocks table (optional reference)
    op.add_column('blocks', sa.Column('dataset_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('blocks', sa.Column('dataset_revision_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_blocks_dataset_id', 'blocks', 'datasets', ['dataset_id'], ['dataset_id'], ondelete='SET NULL')
    op.create_foreign_key('fk_blocks_dataset_revision_id', 'blocks', 'dataset_revisions', ['dataset_revision_id'], ['revision_id'], ondelete='SET NULL')
    op.create_index('ix_blocks_dataset_id', 'blocks', ['dataset_id'], unique=False)


def downgrade() -> None:
    """
    Remove Dataset and DatasetRevision tables.
    """
    # Remove blocks.dataset_id references
    op.drop_index('ix_blocks_dataset_id', table_name='blocks')
    op.drop_constraint('fk_blocks_dataset_revision_id', 'blocks', type_='foreignkey')
    op.drop_constraint('fk_blocks_dataset_id', 'blocks', type_='foreignkey')
    op.drop_column('blocks', 'dataset_revision_id')
    op.drop_column('blocks', 'dataset_id')

    # Drop dataset_revisions table
    op.drop_index('ix_dataset_revisions_dataset_revision', table_name='dataset_revisions')
    op.drop_index(op.f('ix_dataset_revisions_dataset_id'), table_name='dataset_revisions')
    op.drop_table('dataset_revisions')

    # Drop datasets table
    op.drop_index('ix_datasets_company_not_deleted', table_name='datasets')
    op.drop_index(op.f('ix_datasets_company_id'), table_name='datasets')
    op.drop_table('datasets')


