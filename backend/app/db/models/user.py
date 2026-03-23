from sqlalchemy import JSON, BigInteger, Boolean, String
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

    role_bindings = relationship(
        "RoleBinding",
        back_populates="user",
        foreign_keys="[RoleBinding.user_id]",
        lazy="selectin",
    )
    refresh_tokens = relationship("RefreshToken", back_populates="user", lazy="noload")
