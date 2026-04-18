from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, String, UniqueConstraint, text
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
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    valid_from: Mapped[str | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[str | None] = mapped_column(Date, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "requirement_item_id", "shared_element_id", "version",
            name="uq_item_shared_element_version",
        ),
        Index(
            "uq_current_mapping_per_pair",
            "requirement_item_id",
            "shared_element_id",
            unique=True,
            sqlite_where=text("is_current = 1"),
            postgresql_where=text("is_current"),
        ),
    )
