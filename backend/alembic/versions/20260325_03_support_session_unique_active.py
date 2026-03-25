"""enforce one active support session per platform admin

Revision ID: 20260325_03
Revises: 20260325_02
Create Date: 2026-03-25 18:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260325_03"
down_revision: str | None = "20260325_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "uq_support_sessions_active_admin"


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return table_name in _inspector().get_table_names()


def _has_index(table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in _inspector().get_indexes(table_name))


def _deduplicate_active_support_sessions() -> None:
    bind = op.get_bind()
    support_sessions = sa.table(
        "support_sessions",
        sa.column("id", sa.Integer()),
        sa.column("platform_admin_id", sa.Integer()),
        sa.column("started_at", sa.DateTime(timezone=True)),
        sa.column("ended_at", sa.DateTime(timezone=True)),
        sa.column("is_active", sa.Boolean()),
    )

    rows = bind.execute(
        sa.select(
            support_sessions.c.id,
            support_sessions.c.platform_admin_id,
            support_sessions.c.started_at,
        )
        .where(support_sessions.c.is_active.is_(True))
        .order_by(
            support_sessions.c.platform_admin_id,
            support_sessions.c.started_at.desc().nullslast(),
            support_sessions.c.id.desc(),
        )
    ).fetchall()

    seen_admins: set[int] = set()
    duplicate_ids: list[int] = []
    for row in rows:
        if row.platform_admin_id in seen_admins:
            duplicate_ids.append(row.id)
            continue
        seen_admins.add(row.platform_admin_id)

    if duplicate_ids:
        bind.execute(
            support_sessions.update()
            .where(support_sessions.c.id.in_(duplicate_ids))
            .values(is_active=False, ended_at=sa.func.now())
        )


def upgrade() -> None:
    if not _has_table("support_sessions"):
        return

    _deduplicate_active_support_sessions()

    if not _has_index("support_sessions", INDEX_NAME):
        op.create_index(
            INDEX_NAME,
            "support_sessions",
            ["platform_admin_id"],
            unique=True,
            postgresql_where=sa.text("is_active = true"),
            sqlite_where=sa.text("is_active = 1"),
        )


def downgrade() -> None:
    if not _has_table("support_sessions"):
        return

    if _has_index("support_sessions", INDEX_NAME):
        op.drop_index(INDEX_NAME, table_name="support_sessions")
