"""extend refresh tokens with server-side session metadata

Revision ID: 20260324_02
Revises: 20260324_01
Create Date: 2026-03-24 18:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260324_02"
down_revision: Union[str, None] = "20260324_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return table_name in _inspector().get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in _inspector().get_columns(table_name))


def _has_index(table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in _inspector().get_indexes(table_name))


def _ensure_column(table_name: str, column: sa.Column) -> None:
    if not _has_column(table_name, column.name):
        op.add_column(table_name, column)


def _ensure_index(
    table_name: str,
    index_name: str,
    columns: list[str],
    *,
    unique: bool = False,
) -> None:
    if not _has_index(table_name, index_name):
        op.create_index(index_name, table_name, columns, unique=unique)


def upgrade() -> None:
    if not _has_table("refresh_tokens"):
        return

    _ensure_column("refresh_tokens", sa.Column("token_jti", sa.String(length=128), nullable=True))
    _ensure_column("refresh_tokens", sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True))
    _ensure_column("refresh_tokens", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
    _ensure_column("refresh_tokens", sa.Column("revoked_reason", sa.String(length=64), nullable=True))
    _ensure_column("refresh_tokens", sa.Column("rotated_from_id", sa.Integer(), nullable=True))
    _ensure_column("refresh_tokens", sa.Column("ip_address", sa.String(length=64), nullable=True))
    _ensure_column("refresh_tokens", sa.Column("user_agent", sa.String(length=512), nullable=True))

    _ensure_index(
        "refresh_tokens",
        op.f("ix_refresh_tokens_token_jti"),
        ["token_jti"],
        unique=True,
    )


def downgrade() -> None:
    if not _has_table("refresh_tokens"):
        return

    if _has_index("refresh_tokens", op.f("ix_refresh_tokens_token_jti")):
        op.drop_index(op.f("ix_refresh_tokens_token_jti"), table_name="refresh_tokens")
