"""enforce one pending invitation per organization/email

Revision ID: 20260325_05
Revises: 20260325_04
Create Date: 2026-03-25 22:55:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260325_05"
down_revision: str | None = "20260325_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "uq_pending_user_invitation"


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return table_name in _inspector().get_table_names()


def _has_index(table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in _inspector().get_indexes(table_name))


def _has_column(table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in _inspector().get_columns(table_name))


def _deduplicate_pending_invitations() -> None:
    bind = op.get_bind()
    has_last_sent_at = _has_column("user_invitations", "last_sent_at")
    invitations = sa.table(
        "user_invitations",
        sa.column("id", sa.Integer()),
        sa.column("organization_id", sa.Integer()),
        sa.column("email", sa.String()),
        sa.column("status", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("last_sent_at", sa.DateTime(timezone=True)),
    )

    order_by = [
        invitations.c.organization_id,
        invitations.c.email,
    ]
    if has_last_sent_at:
        order_by.append(invitations.c.last_sent_at.desc().nullslast())
    order_by.extend(
        [
            invitations.c.created_at.desc().nullslast(),
            invitations.c.id.desc(),
        ]
    )

    selected_columns = [
        invitations.c.id,
        invitations.c.organization_id,
        invitations.c.email,
        invitations.c.created_at,
    ]
    if has_last_sent_at:
        selected_columns.append(invitations.c.last_sent_at)

    rows = bind.execute(
        sa.select(*selected_columns)
        .where(invitations.c.status == "pending")
        .order_by(*order_by)
    ).fetchall()

    seen_keys: set[tuple[int, str]] = set()
    duplicate_ids: list[int] = []
    for row in rows:
        key = (row.organization_id, row.email)
        if key in seen_keys:
            duplicate_ids.append(row.id)
            continue
        seen_keys.add(key)

    if duplicate_ids:
        bind.execute(
            invitations.update()
            .where(invitations.c.id.in_(sorted(set(duplicate_ids))))
            .values(status="cancelled")
        )


def upgrade() -> None:
    if not _has_table("user_invitations"):
        return

    _deduplicate_pending_invitations()

    if not _has_index("user_invitations", INDEX_NAME):
        op.create_index(
            INDEX_NAME,
            "user_invitations",
            ["organization_id", "email"],
            unique=True,
            postgresql_where=sa.text("status = 'pending'"),
            sqlite_where=sa.text("status = 'pending'"),
        )


def downgrade() -> None:
    if not _has_table("user_invitations"):
        return

    if _has_index("user_invitations", INDEX_NAME):
        op.drop_index(INDEX_NAME, table_name="user_invitations")
