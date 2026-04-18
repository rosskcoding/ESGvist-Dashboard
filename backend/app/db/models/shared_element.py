from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin


class SharedElement(Base, TimestampMixin):
    __tablename__ = "shared_elements"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    concept_domain: Mapped[str | None] = mapped_column(String, nullable=True)  # emissions|energy|water|waste|...
    default_value_type: Mapped[str | None] = mapped_column(String, nullable=True)
    default_unit_code: Mapped[str | None] = mapped_column(String, nullable=True)

    # Versioning (TZ-Admin 3.14)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    valid_from: Mapped[str | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[str | None] = mapped_column(Date, nullable=True)
    element_key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    owner_layer: Mapped[str] = mapped_column(String, default="internal_catalog", nullable=False)
    organization_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_element_key: Mapped[str | None] = mapped_column(String, nullable=True)
    lifecycle_status: Mapped[str] = mapped_column(String, default="active", nullable=False)
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    dimensions = relationship("SharedElementDimension", back_populates="shared_element", lazy="noload")


class SharedElementDimension(Base, TimestampMixin):
    __tablename__ = "shared_element_dimensions"

    id: Mapped[int] = mapped_column(primary_key=True)
    shared_element_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("shared_elements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dimension_type: Mapped[str] = mapped_column(String, nullable=False)  # scope|gas|category|facility|geography
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    shared_element = relationship("SharedElement", back_populates="dimensions")

    __table_args__ = (
        UniqueConstraint(
            "shared_element_id", "dimension_type",
            name="uq_shared_element_dimension",
        ),
    )
