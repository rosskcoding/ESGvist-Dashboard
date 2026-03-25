"""enforce a single default boundary per organization

Revision ID: 20260325_01
Revises: 20260324_03
Create Date: 2026-03-25 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260325_01"
down_revision: str | None = "20260324_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return table_name in _inspector().get_table_names()


def _has_index(table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in _inspector().get_indexes(table_name))


def _normalize_duplicate_defaults() -> None:
    bind = op.get_bind()
    boundary_definitions = sa.table(
        "boundary_definitions",
        sa.column("id", sa.Integer()),
        sa.column("organization_id", sa.Integer()),
        sa.column("is_default", sa.Boolean()),
    )

    rows = bind.execute(
        sa.select(
            boundary_definitions.c.id,
            boundary_definitions.c.organization_id,
        )
        .where(boundary_definitions.c.is_default.is_(True))
        .order_by(boundary_definitions.c.organization_id, boundary_definitions.c.id)
    ).fetchall()

    seen_org_ids: set[int] = set()
    for row in rows:
        if row.organization_id in seen_org_ids:
            bind.execute(
                boundary_definitions.update()
                .where(boundary_definitions.c.id == row.id)
                .values(is_default=False)
            )
            continue
        seen_org_ids.add(row.organization_id)


def upgrade() -> None:
    if not _has_table("boundary_definitions"):
        return

    _normalize_duplicate_defaults()

    if not _has_index("boundary_definitions", "uq_boundary_default_per_org"):
        op.create_index(
            "uq_boundary_default_per_org",
            "boundary_definitions",
            ["organization_id"],
            unique=True,
            sqlite_where=sa.text("is_default = 1"),
            postgresql_where=sa.text("is_default"),
        )


def downgrade() -> None:
    if not _has_table("boundary_definitions"):
        return

    if _has_index("boundary_definitions", "uq_boundary_default_per_org"):
        op.drop_index("uq_boundary_default_per_org", table_name="boundary_definitions")
