"""finalize hashed refresh token storage

Revision ID: 20260325_06
Revises: 20260325_05
Create Date: 2026-03-25 23:35:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from jose import jwt

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260325_06"
down_revision: str | None = "20260325_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return table_name in _inspector().get_table_names()


def _looks_hashed(token: str | None) -> bool:
    if not token or len(token) != 64:
        return False
    return all(char in "0123456789abcdef" for char in token)


def _hash_token(token: str) -> str:
    import hashlib

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _decode_refresh_jti(token: str) -> str | None:
    from app.core.config import settings

    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except Exception:
        return None
    if payload.get("token_type") != "refresh":
        return None
    jti = payload.get("jti")
    return str(jti) if jti else None


def upgrade() -> None:
    if not _has_table("refresh_tokens"):
        return

    bind = op.get_bind()
    refresh_tokens = sa.table(
        "refresh_tokens",
        sa.column("id", sa.Integer()),
        sa.column("token", sa.String()),
        sa.column("token_jti", sa.String()),
    )

    rows = bind.execute(
        sa.select(
            refresh_tokens.c.id,
            refresh_tokens.c.token,
            refresh_tokens.c.token_jti,
        )
    ).fetchall()

    for row in rows:
        updates: dict[str, str] = {}
        if row.token and not _looks_hashed(row.token):
            updates["token"] = _hash_token(row.token)
            if not row.token_jti:
                token_jti = _decode_refresh_jti(row.token)
                if token_jti:
                    updates["token_jti"] = token_jti
        elif row.token and row.token_jti is None:
            # Leave already-hashed rows untouched if jti is unknown.
            pass

        if updates:
            bind.execute(
                refresh_tokens.update()
                .where(refresh_tokens.c.id == row.id)
                .values(**updates)
            )


def downgrade() -> None:
    # Raw refresh tokens are intentionally not restorable.
    return None
