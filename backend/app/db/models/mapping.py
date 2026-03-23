from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin


class RequirementItemSharedElement(Base, TimestampMixin):
    __tablename__ = "requirement_item_shared_elements"

    id: Mapped[int] = mapped_column(primary_key=True)
    requirement_item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("requirement_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    shared_element_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("shared_elements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mapping_type: Mapped[str] = mapped_column(
        String, nullable=False, default="full"
    )  # full | partial | derived

    __table_args__ = (
        UniqueConstraint(
            "requirement_item_id", "shared_element_id",
            name="uq_item_shared_element",
        ),
    )
