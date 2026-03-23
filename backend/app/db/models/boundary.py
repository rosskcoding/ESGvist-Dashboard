from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin


class BoundaryDefinition(Base, TimestampMixin):
    __tablename__ = "boundary_definitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    boundary_type: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    inclusion_rules: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    consolidation_rules: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class BoundaryMembership(Base, TimestampMixin):
    __tablename__ = "boundary_memberships"

    id: Mapped[int] = mapped_column(primary_key=True)
    boundary_definition_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("boundary_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("company_entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    included: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    inclusion_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    inclusion_source: Mapped[str] = mapped_column(String, default="automatic", nullable=False)
    consolidation_method: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (
        UniqueConstraint("boundary_definition_id", "entity_id", name="uq_boundary_membership"),
    )
