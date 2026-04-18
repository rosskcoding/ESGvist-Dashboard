"""restore notification context metadata migration

Revision ID: 20260415_02
Revises: 20260415_01
Create Date: 2026-04-15 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260415_02"
down_revision: str | None = "20260415_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_column(table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in _inspector().get_columns(table_name))


def upgrade() -> None:
    if not _has_column("notifications", "context"):
        op.add_column("notifications", sa.Column("context", sa.JSON(), nullable=True))


def downgrade() -> None:
    if _has_column("notifications", "context"):
        op.drop_column("notifications", "context")
