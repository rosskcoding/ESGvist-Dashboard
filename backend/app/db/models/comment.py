from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    data_point_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("data_points.id", ondelete="CASCADE"), nullable=True, index=True
    )
    requirement_item_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("requirement_items.id", ondelete="CASCADE"), nullable=True, index=True
    )
    parent_comment_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    comment_type: Mapped[str] = mapped_column(
        String, default="general", nullable=False
    )  # question|issue|suggestion|resolution|general
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
