"""Add translation_daily_budget_usd to companies.

Revision ID: 20260105_0100
Revises: 20260101_1500
Create Date: 2026-01-05

Adds per-company daily translation budget limit.
0 = use platform default (`settings.translation_daily_budget_usd`).
If the effective budget is 0, budget enforcement is disabled (unlimited).
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision = "20260105_0100"
down_revision = "20260101_1500"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add translation_daily_budget_usd column to companies."""
    op.add_column(
        "companies",
        sa.Column(
            "translation_daily_budget_usd",
            sa.Float(),
            nullable=False,
            server_default="0",
            comment="Daily translation budget in USD (0 = use platform default; effective 0 disables enforcement)",
        ),
    )


def downgrade() -> None:
    """Remove translation_daily_budget_usd column from companies."""
    op.drop_column("companies", "translation_daily_budget_usd")

