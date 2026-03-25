"""drop redundant project -> boundary_snapshot foreign key

Revision ID: 20260325_08
Revises: 20260325_07
Create Date: 2026-03-25 17:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260325_08"
down_revision: str | None = "20260325_07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return table_name in _inspector().get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in _inspector().get_columns(table_name))


def upgrade() -> None:
    if not _has_table("reporting_projects"):
        return
    if not _has_column("reporting_projects", "boundary_snapshot_id"):
        return

    with op.batch_alter_table("reporting_projects") as batch_op:
        batch_op.drop_column("boundary_snapshot_id")


def downgrade() -> None:
    if not _has_table("reporting_projects"):
        return
    if _has_column("reporting_projects", "boundary_snapshot_id"):
        return

    with op.batch_alter_table("reporting_projects") as batch_op:
        batch_op.add_column(
            sa.Column(
                "boundary_snapshot_id",
                sa.Integer(),
                sa.ForeignKey("boundary_snapshots.id", ondelete="SET NULL"),
                nullable=True,
            )
        )
