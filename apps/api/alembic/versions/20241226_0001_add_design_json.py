"""Add design_json column to reports table.

Revision ID: 20241226_0001
Revises: 20241225_0004
Create Date: 2024-12-26

"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20241226_0001"
down_revision: str | None = "20241225_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add design_json JSONB column to reports."""
    op.add_column(
        "reports",
        sa.Column(
            "design_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Remove design_json column from reports."""
    op.drop_column("reports", "design_json")




