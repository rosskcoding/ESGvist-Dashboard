from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notification_prefs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    totp_secret: Mapped[str | None] = mapped_column(String, nullable=True)
    totp_pending_secret: Mapped[str | None] = mapped_column(String, nullable=True)
    totp_backup_codes: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    totp_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    role_bindings = relationship(
        "RoleBinding",
        back_populates="user",
        foreign_keys="[RoleBinding.user_id]",
        lazy="selectin",
    )
    refresh_tokens = relationship("RefreshToken", back_populates="user", lazy="noload")
