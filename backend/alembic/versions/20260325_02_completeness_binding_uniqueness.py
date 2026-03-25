"""enforce unique requirement-item to data-point bindings

Revision ID: 20260325_02
Revises: 20260325_01
Create Date: 2026-03-25 16:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260325_02"
down_revision: str | None = "20260325_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return table_name in _inspector().get_table_names()


def _has_unique_constraint(table_name: str, constraint_name: str) -> bool:
    return any(
        constraint["name"] == constraint_name
        for constraint in _inspector().get_unique_constraints(table_name)
    )


def _deduplicate_bindings() -> None:
    bind = op.get_bind()
    bindings = sa.table(
        "requirement_item_data_points",
        sa.column("id", sa.Integer()),
        sa.column("reporting_project_id", sa.Integer()),
        sa.column("requirement_item_id", sa.Integer()),
        sa.column("data_point_id", sa.Integer()),
    )
    rows = bind.execute(
        sa.select(
            bindings.c.id,
            bindings.c.reporting_project_id,
            bindings.c.requirement_item_id,
            bindings.c.data_point_id,
        ).order_by(bindings.c.id)
    ).fetchall()

    seen_keys: set[tuple[int, int, int]] = set()
    duplicate_ids: list[int] = []
    for row in rows:
        key = (
            row.reporting_project_id,
            row.requirement_item_id,
            row.data_point_id,
        )
        if key in seen_keys:
            duplicate_ids.append(row.id)
            continue
        seen_keys.add(key)

    if duplicate_ids:
        bind.execute(
            bindings.delete().where(bindings.c.id.in_(duplicate_ids))
        )


def upgrade() -> None:
    if not _has_table("requirement_item_data_points"):
        return

    _deduplicate_bindings()

    if not _has_unique_constraint(
        "requirement_item_data_points",
        "uq_requirement_item_data_point",
    ):
        with op.batch_alter_table("requirement_item_data_points") as batch_op:
            batch_op.create_unique_constraint(
                "uq_requirement_item_data_point",
                ["reporting_project_id", "requirement_item_id", "data_point_id"],
            )


def downgrade() -> None:
    if not _has_table("requirement_item_data_points"):
        return

    if _has_unique_constraint(
        "requirement_item_data_points",
        "uq_requirement_item_data_point",
    ):
        with op.batch_alter_table("requirement_item_data_points") as batch_op:
            batch_op.drop_constraint("uq_requirement_item_data_point", type_="unique")
