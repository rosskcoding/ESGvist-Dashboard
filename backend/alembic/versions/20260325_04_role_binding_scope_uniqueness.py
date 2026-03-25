"""enforce one role binding per user scope

Revision ID: 20260325_04
Revises: 20260325_03
Create Date: 2026-03-25 21:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260325_04"
down_revision: str | None = "20260325_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "uq_user_scope"
ROLE_PRIORITY = {
    "platform_admin": 0,
    "admin": 1,
    "esg_manager": 2,
    "reviewer": 3,
    "collector": 4,
    "auditor": 5,
}


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return table_name in _inspector().get_table_names()


def _has_unique_scope_invariant(table_name: str) -> bool:
    inspector = _inspector()
    expected = ["user_id", "scope_type", "scope_id"]

    for constraint in inspector.get_unique_constraints(table_name):
        if constraint.get("name") == INDEX_NAME:
            return True
        if constraint.get("column_names") == expected:
            return True

    for index in inspector.get_indexes(table_name):
        if not index.get("unique"):
            continue
        if index.get("name") == INDEX_NAME:
            return True
        if index.get("column_names") == expected:
            return True
    return False


def _deduplicate_role_bindings() -> None:
    bind = op.get_bind()
    role_bindings = sa.table(
        "role_bindings",
        sa.column("id", sa.Integer()),
        sa.column("user_id", sa.Integer()),
        sa.column("role", sa.String()),
        sa.column("scope_type", sa.String()),
        sa.column("scope_id", sa.Integer()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )

    rows = bind.execute(
        sa.select(
            role_bindings.c.id,
            role_bindings.c.user_id,
            role_bindings.c.role,
            role_bindings.c.scope_type,
            role_bindings.c.scope_id,
            role_bindings.c.created_at,
        ).order_by(
            role_bindings.c.user_id,
            role_bindings.c.scope_type,
            role_bindings.c.scope_id,
            role_bindings.c.created_at.desc().nullslast(),
            role_bindings.c.id.desc(),
        )
    ).fetchall()

    seen_scopes: dict[tuple[int, str, int | None], tuple[int, int]] = {}
    duplicate_ids: list[int] = []
    for row in rows:
        key = (row.user_id, row.scope_type, row.scope_id)
        priority = ROLE_PRIORITY.get(row.role, 99)
        existing = seen_scopes.get(key)
        if existing is None:
            seen_scopes[key] = (priority, row.id)
            continue
        existing_priority, existing_id = existing
        if priority < existing_priority:
            duplicate_ids.append(existing_id)
            seen_scopes[key] = (priority, row.id)
        else:
            duplicate_ids.append(row.id)

    if duplicate_ids:
        bind.execute(
            role_bindings.delete().where(role_bindings.c.id.in_(sorted(set(duplicate_ids))))
        )


def upgrade() -> None:
    if not _has_table("role_bindings"):
        return

    _deduplicate_role_bindings()

    if not _has_unique_scope_invariant("role_bindings"):
        op.create_index(
            INDEX_NAME,
            "role_bindings",
            ["user_id", "scope_type", "scope_id"],
            unique=True,
        )


def downgrade() -> None:
    if not _has_table("role_bindings"):
        return

    if _has_unique_scope_invariant("role_bindings"):
        op.drop_index(INDEX_NAME, table_name="role_bindings")
