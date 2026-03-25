from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin


class RoleBinding(Base, TimestampMixin):
    __tablename__ = "role_bindings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    scope_type: Mapped[str] = mapped_column(String, nullable=False)  # 'platform' | 'organization'
    scope_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    created_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    user = relationship("User", back_populates="role_bindings", foreign_keys=[user_id])

    __table_args__ = (
        # One role per user per scope — prevents multi-role ambiguity
        UniqueConstraint("user_id", "scope_type", "scope_id", name="uq_user_scope"),
        # Keep the old granular unique for backward compat during migration
        UniqueConstraint("user_id", "role", "scope_type", "scope_id", name="uq_role_binding"),
        CheckConstraint(
            "(scope_type = 'platform' AND scope_id IS NULL) OR "
            "(scope_type = 'organization' AND scope_id IS NOT NULL)",
            name="chk_scope_id_required",
        ),
        CheckConstraint(
            "(scope_type = 'platform' AND role IN ('platform_admin', 'framework_admin')) OR "
            "(scope_type = 'organization' AND role NOT IN ('platform_admin', 'framework_admin'))",
            name="chk_platform_role",
        ),
        CheckConstraint(
            "role IN ('platform_admin', 'framework_admin', 'admin', 'esg_manager', 'reviewer', 'collector', 'auditor')",
            name="chk_role_enum",
        ),
        CheckConstraint(
            "scope_type IN ('platform', 'organization')",
            name="chk_scope_type_enum",
        ),
    )
