"""Add refresh_tokens table for secure token management.

Security features:
- Server-side refresh token storage
- Token revocation support
- Token rotation (one-time use)
- Token family tracking for theft detection

Revision ID: add_refresh_tokens_001
Revises: fix_asset_url_null_002
Create Date: 2024-12-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "add_refresh_tokens_001"
down_revision: Union[str, None] = "3beb5952c3e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create refresh_tokens table."""
    op.create_table(
        "refresh_tokens",
        sa.Column(
            "token_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            primary_key=True,
        ),
        sa.Column(
            "jti",
            sa.String(64),
            nullable=False,
            unique=True,
            index=True,
            comment="JWT ID for token identification",
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "family_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            index=True,
            comment="Token family for theft detection",
        ),
        sa.Column(
            "is_revoked",
            sa.Boolean(),
            nullable=False,
            default=False,
            comment="True if token was explicitly revoked",
        ),
        sa.Column(
            "is_used",
            sa.Boolean(),
            nullable=False,
            default=False,
            comment="True if token was used for refresh (rotation)",
        ),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "expires_at_utc",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Token expiration time",
        ),
        sa.Column(
            "user_agent",
            sa.Text(),
            nullable=True,
            comment="Browser/client user agent",
        ),
        sa.Column(
            "ip_address",
            sa.String(45),
            nullable=True,
            comment="Client IP address",
        ),
    )

    # Create composite index for common query patterns
    op.create_index(
        "ix_refresh_tokens_user_valid",
        "refresh_tokens",
        ["user_id", "is_revoked", "is_used"],
    )


def downgrade() -> None:
    """Drop refresh_tokens table."""
    op.drop_index("ix_refresh_tokens_user_valid", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

