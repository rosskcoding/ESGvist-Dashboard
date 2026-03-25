from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin


class RequirementItemDataPoint(Base, TimestampMixin):
    """Binding: requirement_item ↔ data_point within a project."""
    __tablename__ = "requirement_item_data_points"

    id: Mapped[int] = mapped_column(primary_key=True)
    reporting_project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("reporting_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requirement_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("requirement_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    data_point_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("data_points.id", ondelete="CASCADE"), nullable=False, index=True
    )
    binding_type: Mapped[str] = mapped_column(String, default="direct", nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "reporting_project_id",
            "requirement_item_id",
            "data_point_id",
            name="uq_requirement_item_data_point",
        ),
    )


class RequirementItemStatus(Base, TimestampMixin):
    __tablename__ = "requirement_item_statuses"

    id: Mapped[int] = mapped_column(primary_key=True)
    reporting_project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("reporting_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requirement_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("requirement_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String, nullable=False)  # missing|partial|complete|not_applicable
    status_reason: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "reporting_project_id", "requirement_item_id",
            name="uq_item_status",
        ),
    )


class DisclosureRequirementStatus(Base, TimestampMixin):
    __tablename__ = "disclosure_requirement_statuses"

    id: Mapped[int] = mapped_column(primary_key=True)
    reporting_project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("reporting_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    disclosure_requirement_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("disclosure_requirements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String, nullable=False)  # missing|partial|complete
    completion_percent: Mapped[float] = mapped_column(Float, default=0, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "reporting_project_id", "disclosure_requirement_id",
            name="uq_disclosure_status",
        ),
    )
