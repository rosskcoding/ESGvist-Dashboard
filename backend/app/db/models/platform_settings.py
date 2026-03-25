"""Persistent platform-level settings (singleton row).

Stores configuration that platform admins can change at runtime and
which must survive restarts and be consistent across workers.
"""

from sqlalchemy import Boolean, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin


class PlatformSettings(Base, TimestampMixin):
    __tablename__ = "platform_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    allow_self_registration: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
