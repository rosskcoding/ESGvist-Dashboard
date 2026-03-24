"""hash persisted refresh token values

Revision ID: 20260324_03
Revises: 20260324_02
Create Date: 2026-03-24 23:30:00.000000
"""

import hashlib
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260324_03"
down_revision: Union[str, None] = "20260324_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return table_name in _inspector().get_table_names()


def upgrade() -> None:
    if not _has_table("refresh_tokens"):
        return

    bind = op.get_bind()
    refresh_tokens = sa.table(
        "refresh_tokens",
        sa.column("id", sa.Integer()),
        sa.column("token", sa.String()),
    )
    rows = bind.execute(sa.select(refresh_tokens.c.id, refresh_tokens.c.token)).fetchall()
    for row in rows:
        token = row.token
        if not token:
            continue
        if len(token) == 64 and all(char in "0123456789abcdef" for char in token):
            continue
        bind.execute(
            refresh_tokens.update()
            .where(refresh_tokens.c.id == row.id)
            .values(token=hashlib.sha256(token.encode("utf-8")).hexdigest())
        )


def downgrade() -> None:
    # Irreversible: raw refresh tokens are intentionally not recoverable.
    return
