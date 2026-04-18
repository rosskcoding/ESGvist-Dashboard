from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin


class CompanyEntity(Base, TimestampMixin):
    __tablename__ = "company_entities"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_entity_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("company_entities.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    code: Mapped[str | None] = mapped_column(String, nullable=True)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    country: Mapped[str | None] = mapped_column(String, nullable=True)
    jurisdiction: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)
    valid_from: Mapped[str | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[str | None] = mapped_column(Date, nullable=True)
    default_collector_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    default_reviewer_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    children = relationship("CompanyEntity", lazy="noload", overlaps="parent")
    parent = relationship(
        "CompanyEntity", remote_side="CompanyEntity.id", lazy="noload"
    )

    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('parent_company','legal_entity','branch','joint_venture','associate','facility','business_unit')",
            name="chk_entity_type",
        ),
        CheckConstraint(
            "status IN ('active','inactive','disposed')",
            name="chk_entity_status",
        ),
    )


class OwnershipLink(Base, TimestampMixin):
    __tablename__ = "ownership_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_entity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("company_entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    child_entity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("company_entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ownership_percent: Mapped[float] = mapped_column(Numeric(7, 4), nullable=False)
    ownership_type: Mapped[str] = mapped_column(String, default="direct", nullable=False)
    valid_from: Mapped[str | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[str | None] = mapped_column(Date, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "parent_entity_id != child_entity_id",
            name="chk_no_self_ownership",
        ),
        CheckConstraint(
            "ownership_type IN ('direct','indirect','beneficial')",
            name="chk_ownership_type",
        ),
    )


class ControlLink(Base, TimestampMixin):
    __tablename__ = "control_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    controlling_entity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("company_entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    controlled_entity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("company_entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    control_type: Mapped[str] = mapped_column(String, nullable=False)
    is_controlled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    valid_from: Mapped[str | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[str | None] = mapped_column(Date, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "controlling_entity_id != controlled_entity_id",
            name="chk_no_self_control",
        ),
        CheckConstraint(
            "control_type IN ('financial_control','operational_control','management_control','significant_influence')",
            name="chk_control_type",
        ),
    )
