from sqlalchemy import ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin


class RequirementDelta(Base, TimestampMixin):
    __tablename__ = "requirement_deltas"

    id: Mapped[int] = mapped_column(primary_key=True)
    requirement_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("requirement_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    standard_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("standards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    delta_type: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    condition: Mapped[dict | None] = mapped_column(JSON, nullable=True)
