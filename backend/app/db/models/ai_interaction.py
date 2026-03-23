from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Boolean, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base


class AIInteraction(Base):
    __tablename__ = "ai_interactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    role: Mapped[str] = mapped_column(String, nullable=False)
    screen: Mapped[str | None] = mapped_column(String, nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    context_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    question: Mapped[str | None] = mapped_column(String, nullable=True)
    response_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    tokens_input: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_output: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gate_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    gate_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
