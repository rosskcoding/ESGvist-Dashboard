from sqlalchemy import BigInteger, Boolean, CheckConstraint, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String, nullable=True)
    registration_number: Mapped[str | None] = mapped_column(String, nullable=True)
    country: Mapped[str | None] = mapped_column(String, nullable=True)
    jurisdiction: Mapped[str | None] = mapped_column(String, nullable=True)
    industry: Mapped[str | None] = mapped_column(String, nullable=True)
    default_currency: Mapped[str] = mapped_column(String, default="USD", nullable=False)
    default_reporting_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_standards: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    default_consolidation_approach: Mapped[str | None] = mapped_column(String, nullable=True)
    default_ghg_scope_approach: Mapped[str | None] = mapped_column(String, nullable=True)
    allow_password_login: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_sso_login: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    enforce_sso: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    setup_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('active','suspended','archived')", name="chk_org_status"),
    )
