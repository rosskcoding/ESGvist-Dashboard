"""
Refresh Token model for secure token storage and revocation.

Security features:
- Server-side storage enables revocation
- Token rotation (one-time use)
- Device/session tracking
- Family-based revocation (detect token theft)
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class RefreshToken(Base):
    """
    Stored refresh token for revocation and rotation support.

    Security model:
    - Each refresh token has unique jti (JWT ID)
    - Token can only be used once (rotation)
    - Family tracking detects stolen tokens
    - Explicit revocation via is_revoked flag
    """

    __tablename__ = "refresh_tokens"

    token_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # JWT ID - unique identifier embedded in the token
    jti: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
        doc="JWT ID for token identification",
    )

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Token family for rotation tracking
    # All tokens from same login session share family_id
    # If old token is reused, revoke entire family (theft detection)
    family_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
        doc="Token family for theft detection",
    )

    # Token state
    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="True if token was explicitly revoked",
    )

    is_used: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="True if token was used for refresh (rotation)",
    )

    # Timestamps
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    expires_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        doc="Token expiration time",
    )

    # Optional metadata for security audit
    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Browser/client user agent",
    )

    ip_address: Mapped[str | None] = mapped_column(
        String(45),  # IPv6 max length
        nullable=True,
        doc="Client IP address",
    )

    # Relationships
    user: Mapped["User"] = relationship(  # noqa: F821
        "User",
        back_populates="refresh_tokens",
    )

    def __repr__(self) -> str:
        return f"<RefreshToken {self.jti[:8]}... user={self.user_id}>"

    @property
    def is_valid(self) -> bool:
        """Check if token is valid (not revoked, not used, not expired)."""
        now = datetime.now(UTC)
        return (
            not self.is_revoked
            and not self.is_used
            and self.expires_at_utc > now
        )

    def mark_used(self) -> None:
        """Mark token as used (for rotation)."""
        self.is_used = True

    def revoke(self) -> None:
        """Revoke this token."""
        self.is_revoked = True


