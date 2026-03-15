"""Add section structure fields (depth, label_prefix, label_suffix)

Revision ID: 20241225_0001
Revises: 20241224_0002
Create Date: 2024-12-25

Spec reference: 16_Report_Structure.md
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '20241225_0001'
down_revision = '20241224_0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add structure fields to sections table."""

    # Add depth column with default 0
    op.add_column(
        'sections',
        sa.Column('depth', sa.SmallInteger(), nullable=False, server_default='0')
    )

    # Add label_prefix column (optional)
    op.add_column(
        'sections',
        sa.Column('label_prefix', sa.String(20), nullable=True)
    )

    # Add label_suffix column (optional)
    op.add_column(
        'sections',
        sa.Column('label_suffix', sa.String(50), nullable=True)
    )

    # Add check constraint for depth (0-3)
    op.create_check_constraint(
        'chk_section_depth',
        'sections',
        'depth >= 0 AND depth <= 3'
    )

    # Add index for structure queries
    op.create_index(
        'idx_section_structure',
        'sections',
        ['report_id', 'parent_section_id', 'depth', 'order_index']
    )


def downgrade() -> None:
    """Remove structure fields from sections table."""

    # Drop index
    op.drop_index('idx_section_structure', table_name='sections')

    # Drop check constraint
    op.drop_constraint('chk_section_depth', 'sections', type_='check')

    # Drop columns
    op.drop_column('sections', 'label_suffix')
    op.drop_column('sections', 'label_prefix')
    op.drop_column('sections', 'depth')




