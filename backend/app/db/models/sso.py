from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin


class SSOProvider(Base, TimestampMixin):
    __tablename__ = "sso_providers"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    provider_type: Mapped[str] = mapped_column(String, nullable=False)
    auth_url: Mapped[str] = mapped_column(String, nullable=False)
    issuer: Mapped[str | None] = mapped_column(String, nullable=True)
    client_id: Mapped[str] = mapped_column(String, nullable=False)
    client_secret: Mapped[str | None] = mapped_column(String, nullable=True)
    redirect_uri: Mapped[str | None] = mapped_column(String, nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    auto_provision: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    default_role: Mapped[str] = mapped_column(String, default="collector", nullable=False)


class ExternalIdentity(Base, TimestampMixin):
    __tablename__ = "external_identities"
    __table_args__ = (
        UniqueConstraint("sso_provider_id", "external_subject", name="uq_external_identity_subject"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sso_provider_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sso_providers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_subject: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SSOLoginState(Base):
    __tablename__ = "sso_login_states"
    __table_args__ = (
        UniqueConstraint("state", name="uq_sso_login_state"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sso_provider_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sso_providers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    state: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
