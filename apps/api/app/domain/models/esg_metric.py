"""
ESG Metric model for ESG Dashboard pillar.
"""

from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class EsgMetricValueType(str, Enum):
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    STRING = "string"
    DATASET = "dataset"


class EsgMetric(Base, TimestampMixin):
    __tablename__ = "esg_metrics"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_esg_metrics_company_code"),
    )

    metric_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    company_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.company_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_type: Mapped[EsgMetricValueType] = mapped_column(
        SQLEnum(
            EsgMetricValueType,
            native_enum=False,
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    value_schema_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        doc="Future validation/formatting schema for values (MVP: optional)",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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

    def __repr__(self) -> str:
        return f"<EsgMetric {self.metric_id} {self.name!r} type={self.value_type.value}>"

