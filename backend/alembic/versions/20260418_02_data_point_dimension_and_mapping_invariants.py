"""enforce data point dimension and current mapping invariants

Revision ID: 20260418_02
Revises: 20260325_08
Create Date: 2026-04-18 13:05:00.000000
"""

from collections.abc import Sequence
from datetime import date

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260418_02"
down_revision: str | None = "20260325_08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DATA_POINT_DIMENSION_CONSTRAINT = "uq_data_point_dimension_type"
CURRENT_MAPPING_INDEX = "uq_current_mapping_per_pair"


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return table_name in _inspector().get_table_names()


def _has_index(table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in _inspector().get_indexes(table_name))


def _has_unique_constraint(table_name: str, constraint_name: str) -> bool:
    return any(
        constraint["name"] == constraint_name
        for constraint in _inspector().get_unique_constraints(table_name)
    )


def _normalize_dimension_type(dimension_type: str | None) -> str:
    normalized = (dimension_type or "").strip().lower()
    if normalized in {"gas", "gas_type"}:
        return "gas_type"
    return normalized


def _deduplicate_data_point_dimensions() -> None:
    bind = op.get_bind()
    dimensions = sa.table(
        "data_point_dimensions",
        sa.column("id", sa.Integer()),
        sa.column("data_point_id", sa.Integer()),
        sa.column("dimension_type", sa.String()),
    )

    rows = bind.execute(
        sa.select(
            dimensions.c.id,
            dimensions.c.data_point_id,
            dimensions.c.dimension_type,
        ).order_by(
            dimensions.c.data_point_id,
            dimensions.c.id.desc(),
        )
    ).fetchall()

    seen_keys: set[tuple[int, str]] = set()
    duplicate_ids: list[int] = []
    for row in rows:
        normalized_type = _normalize_dimension_type(row.dimension_type)
        key = (row.data_point_id, normalized_type)
        if key in seen_keys:
            duplicate_ids.append(row.id)
            continue
        seen_keys.add(key)
        if row.dimension_type != normalized_type:
            bind.execute(
                dimensions.update()
                .where(dimensions.c.id == row.id)
                .values(dimension_type=normalized_type)
            )

    if duplicate_ids:
        bind.execute(
            dimensions.delete().where(dimensions.c.id.in_(sorted(set(duplicate_ids))))
        )


def _deduplicate_current_mappings() -> None:
    bind = op.get_bind()
    mappings = sa.table(
        "requirement_item_shared_elements",
        sa.column("id", sa.Integer()),
        sa.column("requirement_item_id", sa.Integer()),
        sa.column("shared_element_id", sa.Integer()),
        sa.column("version", sa.Integer()),
        sa.column("is_current", sa.Boolean()),
        sa.column("valid_to", sa.Date()),
    )

    rows = bind.execute(
        sa.select(
            mappings.c.id,
            mappings.c.requirement_item_id,
            mappings.c.shared_element_id,
            mappings.c.version,
            mappings.c.valid_to,
        )
        .where(mappings.c.is_current.is_(True))
        .order_by(
            mappings.c.requirement_item_id,
            mappings.c.shared_element_id,
            mappings.c.version.desc(),
            mappings.c.id.desc(),
        )
    ).fetchall()

    seen_keys: set[tuple[int, int]] = set()
    retire_ids: list[int] = []
    for row in rows:
        key = (row.requirement_item_id, row.shared_element_id)
        if key in seen_keys:
            retire_ids.append(row.id)
            continue
        seen_keys.add(key)

    if retire_ids:
        bind.execute(
            mappings.update()
            .where(mappings.c.id.in_(sorted(set(retire_ids))))
            .values(is_current=False, valid_to=date.today())
        )


def upgrade() -> None:
    if _has_table("data_point_dimensions"):
        _deduplicate_data_point_dimensions()
        if not _has_unique_constraint("data_point_dimensions", DATA_POINT_DIMENSION_CONSTRAINT):
            op.create_unique_constraint(
                DATA_POINT_DIMENSION_CONSTRAINT,
                "data_point_dimensions",
                ["data_point_id", "dimension_type"],
            )

    if _has_table("requirement_item_shared_elements"):
        _deduplicate_current_mappings()
        if not _has_index("requirement_item_shared_elements", CURRENT_MAPPING_INDEX):
            op.create_index(
                CURRENT_MAPPING_INDEX,
                "requirement_item_shared_elements",
                ["requirement_item_id", "shared_element_id"],
                unique=True,
                sqlite_where=sa.text("is_current = 1"),
                postgresql_where=sa.text("is_current"),
            )


def downgrade() -> None:
    if _has_table("requirement_item_shared_elements") and _has_index(
        "requirement_item_shared_elements",
        CURRENT_MAPPING_INDEX,
    ):
        op.drop_index(CURRENT_MAPPING_INDEX, table_name="requirement_item_shared_elements")

    if _has_table("data_point_dimensions") and _has_unique_constraint(
        "data_point_dimensions",
        DATA_POINT_DIMENSION_CONSTRAINT,
    ):
        op.drop_constraint(
            DATA_POINT_DIMENSION_CONSTRAINT,
            "data_point_dimensions",
            type_="unique",
        )
