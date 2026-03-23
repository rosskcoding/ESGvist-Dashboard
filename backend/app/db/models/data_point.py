from sqlalchemy import ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin


class DataPoint(Base, TimestampMixin):
    __tablename__ = "data_points"

    id: Mapped[int] = mapped_column(primary_key=True)
    reporting_project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("reporting_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    shared_element_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("shared_elements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("company_entities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String, default="draft", nullable=False)
    numeric_value: Mapped[float | None] = mapped_column(Numeric(20, 6), nullable=True)
    text_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit_code: Mapped[str | None] = mapped_column(String, nullable=True)
    methodology_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    boundary_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)


class DataPointDimension(Base, TimestampMixin):
    __tablename__ = "data_point_dimensions"

    id: Mapped[int] = mapped_column(primary_key=True)
    data_point_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("data_points.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dimension_type: Mapped[str] = mapped_column(String, nullable=False)
    dimension_value: Mapped[str] = mapped_column(String, nullable=False)
