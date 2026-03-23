from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin


class ReportingProject(Base, TimestampMixin):
    __tablename__ = "reporting_projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="draft", nullable=False)  # draft|active|review|published|archived
    deadline: Mapped[str | None] = mapped_column(Date, nullable=True)
    reporting_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    boundary_definition_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("boundary_definitions.id", ondelete="SET NULL"), nullable=True
    )


class ReportingProjectStandard(Base, TimestampMixin):
    __tablename__ = "reporting_project_standards"

    id: Mapped[int] = mapped_column(primary_key=True)
    reporting_project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("reporting_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    standard_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("standards.id", ondelete="CASCADE"), nullable=False
    )
    is_base_standard: Mapped[bool] = mapped_column(default=False, nullable=False)


class MetricAssignment(Base, TimestampMixin):
    __tablename__ = "metric_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    reporting_project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("reporting_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    shared_element_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("shared_elements.id", ondelete="CASCADE"), nullable=False
    )
    entity_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("company_entities.id", ondelete="SET NULL"), nullable=True
    )
    facility_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("company_entities.id", ondelete="SET NULL"), nullable=True
    )
    collector_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    reviewer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    backup_collector_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    deadline: Mapped[str | None] = mapped_column(Date, nullable=True)
    escalation_after_days: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    status: Mapped[str] = mapped_column(String, default="assigned", nullable=False)
