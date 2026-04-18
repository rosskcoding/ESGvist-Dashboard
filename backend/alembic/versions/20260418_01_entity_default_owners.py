"""add default collector/reviewer to company_entities

Revision ID: 20260418_01
Revises: 20260417_01
Create Date: 2026-04-18 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260418_01"
down_revision: str | None = "20260417_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_column(table_name: str, column_name: str) -> bool:
    return any(
        column["name"] == column_name
        for column in _inspector().get_columns(table_name)
    )


def upgrade() -> None:
    if not _has_column("company_entities", "default_collector_user_id"):
        op.add_column(
            "company_entities",
            sa.Column(
                "default_collector_user_id",
                sa.BigInteger(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
    if not _has_column("company_entities", "default_reviewer_user_id"):
        op.add_column(
            "company_entities",
            sa.Column(
                "default_reviewer_user_id",
                sa.BigInteger(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )


def downgrade() -> None:
    if _has_column("company_entities", "default_reviewer_user_id"):
        op.drop_column("company_entities", "default_reviewer_user_id")
    if _has_column("company_entities", "default_collector_user_id"):
        op.drop_column("company_entities", "default_collector_user_id")
