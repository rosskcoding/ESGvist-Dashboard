"""Add templates table

Revision ID: 20241225_0004
Revises: 20241225_0003_add_report_slug
Create Date: 2024-12-25 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20241225_0004"
down_revision = "20241225_0003"  # add_report_slug
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create templates table."""
    op.create_table(
        "templates",
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("block_type", sa.String(50), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.String(64)),
            server_default="{}",
            nullable=True,
        ),
        sa.Column(
            "template_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("is_system", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at_utc",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("template_id"),
    )

    # Indexes
    op.create_index("ix_templates_scope", "templates", ["scope"])
    op.create_index("ix_templates_block_type", "templates", ["block_type"])
    op.create_index("ix_templates_is_active", "templates", ["is_active"])
    op.create_index(
        "ix_templates_tags",
        "templates",
        ["tags"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    """Drop templates table."""
    op.drop_index("ix_templates_tags", "templates")
    op.drop_index("ix_templates_is_active", "templates")
    op.drop_index("ix_templates_block_type", "templates")
    op.drop_index("ix_templates_scope", "templates")
    op.drop_table("templates")

