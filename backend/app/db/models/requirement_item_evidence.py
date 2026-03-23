from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin


class RequirementItemEvidence(Base, TimestampMixin):
    __tablename__ = "requirement_item_evidences"

    id: Mapped[int] = mapped_column(primary_key=True)
    requirement_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("requirement_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evidence_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("evidences.id", ondelete="CASCADE"), nullable=False, index=True
    )
    linked_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("requirement_item_id", "evidence_id", name="uq_ri_evidence"),
    )
