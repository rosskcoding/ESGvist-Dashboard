"""
ESG Metric assignment models (owners).

MVP:
- One owner per (company, metric).
"""

from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class EsgMetricAssignment(Base, TimestampMixin):
    __tablename__ = "esg_metric_assignments"
    __table_args__ = (
        UniqueConstraint("company_id", "metric_id", name="uq_esg_metric_assignments_company_metric"),
    )

    assignment_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    company_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.company_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    metric_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("esg_metrics.metric_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    owner_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    updated_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    company = relationship("Company")
    metric = relationship("EsgMetric")
    owner_user = relationship("User", foreign_keys=[owner_user_id])

    def __repr__(self) -> str:
        return f"<EsgMetricAssignment {self.assignment_id} metric={self.metric_id} owner={self.owner_user_id}>"

