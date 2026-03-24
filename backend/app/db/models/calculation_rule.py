from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin


class CalculationRule(Base, TimestampMixin):
    __tablename__ = "calculation_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    output_element_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("shared_elements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    formula: Mapped[dict] = mapped_column(JSON, nullable=False)
    # formula: {"op": "sum", "inputs": [{"element_id": 10}, {"element_id": 11}]}
    input_element_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
