from sqlalchemy import JSON, Boolean, Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin


class Standard(Base, TimestampMixin):
    __tablename__ = "standards"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[str | None] = mapped_column(String, nullable=True)
    jurisdiction: Mapped[str | None] = mapped_column(String, nullable=True)
    effective_from: Mapped[str | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[str | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    sections = relationship("StandardSection", back_populates="standard", lazy="noload")
    disclosures = relationship("DisclosureRequirement", back_populates="standard", lazy="noload")


class StandardSection(Base, TimestampMixin):
    __tablename__ = "standard_sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    standard_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("standards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_section_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("standard_sections.id", ondelete="CASCADE"), nullable=True
    )
    code: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    standard = relationship("Standard", back_populates="sections")
    parent = relationship("StandardSection", remote_side=[id], back_populates="children", lazy="noload")
    children = relationship("StandardSection", back_populates="parent", overlaps="parent", lazy="noload")


class DisclosureRequirement(Base, TimestampMixin):
    __tablename__ = "disclosure_requirements"

    id: Mapped[int] = mapped_column(primary_key=True)
    standard_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("standards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("standard_sections.id", ondelete="SET NULL"), nullable=True
    )
    code: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirement_type: Mapped[str] = mapped_column(String, nullable=False)  # quantitative|qualitative|mixed
    mandatory_level: Mapped[str] = mapped_column(String, nullable=False)  # mandatory|conditional|optional
    applicability_rule: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    disclosure_key: Mapped[str | None] = mapped_column(String, nullable=True)

    standard = relationship("Standard", back_populates="disclosures")

    __table_args__ = (
        # unique code within standard
        {"schema": None},
    )
