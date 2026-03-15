"""Add themes table

Revision ID: 20241224_0002
Revises: 20241224_0001
Create Date: 2024-12-24 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '20241224_0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create themes table
    op.create_table(
        'themes',
        sa.Column('theme_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('slug', sa.String(50), nullable=False, unique=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tokens_json', postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at_utc', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at_utc', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Insert default themes
    from uuid import uuid4

    from sqlalchemy.sql import column, table

    from app.domain.models.theme import (
        CORPORATE_BLUE_TOKENS,
        DARK_THEME_TOKENS,
        DEFAULT_THEME_TOKENS,
    )

    themes_table = table(
        "themes",
        column("theme_id", postgresql.UUID(as_uuid=True)),
        column("slug", sa.String(50)),
        column("name", sa.String(100)),
        column("description", sa.Text()),
        column("tokens_json", postgresql.JSONB()),
        column("is_default", sa.Boolean()),
        column("is_active", sa.Boolean()),
    )

    op.bulk_insert(
        themes_table,
        [
            {
                "theme_id": uuid4(),
                "slug": "default",
                "name": "Default Light",
                "description": "Default light theme with blue accent",
                "tokens_json": DEFAULT_THEME_TOKENS,
                "is_default": True,
                "is_active": True,
            },
            {
                "theme_id": uuid4(),
                "slug": "dark",
                "name": "Dark Mode",
                "description": "Dark theme for reduced eye strain",
                "tokens_json": DARK_THEME_TOKENS,
                "is_default": False,
                "is_active": True,
            },
            {
                "theme_id": uuid4(),
                "slug": "corporate-blue",
                "name": "Corporate Blue",
                "description": "Professional corporate theme",
                "tokens_json": CORPORATE_BLUE_TOKENS,
                "is_default": False,
                "is_active": True,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table('themes')

