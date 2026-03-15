"""Add translation prompt fields to platform_ai_settings.

Revision ID: 20260101_1500
Revises: 20260101_1400_extend_translation_units_field_paths
Create Date: 2026-01-01 15:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260101_1500"
down_revision = "20260101_1400"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add translation prompt fields to platform_ai_settings
    op.add_column(
        "platform_ai_settings",
        sa.Column(
            "translation_prompt_reporting",
            sa.Text(),
            nullable=True,
            comment="Custom prompt template for 'reporting' mode translations. NULL = use default.",
        ),
    )
    op.add_column(
        "platform_ai_settings",
        sa.Column(
            "translation_prompt_marketing",
            sa.Text(),
            nullable=True,
            comment="Custom prompt template for 'marketing' mode translations. NULL = use default.",
        ),
    )


def downgrade() -> None:
    op.drop_column("platform_ai_settings", "translation_prompt_marketing")
    op.drop_column("platform_ai_settings", "translation_prompt_reporting")

