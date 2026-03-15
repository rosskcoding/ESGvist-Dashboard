"""Add platform AI settings (global OpenAI key + model).

Revision ID: 20260101_1300
Revises: 20260101_1200
Create Date: 2026-01-01 13:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260101_1300"
down_revision: Union[str, None] = "20260101_1200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Reuse existing enum type created earlier (20251231_0200_add_company_openai_and_ai_usage.py)
    openai_key_status_enum = postgresql.ENUM(
        "active",
        "invalid",
        "disabled",
        name="openai_key_status",
        create_type=False,
    )

    op.create_table(
        "platform_ai_settings",
        sa.Column("settings_id", sa.SmallInteger(), primary_key=True, nullable=False),
        sa.Column("openai_api_key_encrypted", sa.Text(), nullable=True),
        sa.Column(
            "openai_key_status",
            openai_key_status_enum,
            nullable=False,
            server_default="disabled",
        ),
        sa.Column("openai_key_last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("openai_model", sa.String(length=100), nullable=False, server_default="gpt-4o-mini"),
        sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # Insert singleton row (id=1) if not exists.
    op.execute(
        "INSERT INTO platform_ai_settings (settings_id, openai_key_status, openai_model) "
        "VALUES (1, 'disabled', 'gpt-4o-mini') "
        "ON CONFLICT (settings_id) DO NOTHING"
    )


def downgrade() -> None:
    op.drop_table("platform_ai_settings")


