"""Immutable version history for data point value changes.

A new DataPointVersion row is created automatically whenever a data point's
value or status changes, preserving a full audit trail that reviewers and
auditors can inspect.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base


class DataPointVersion(Base):
    __tablename__ = "data_point_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    data_point_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("data_points.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    numeric_value: Mapped[float | None] = mapped_column(Numeric(20, 6), nullable=True)
    text_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit_code: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    changed_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    change_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
