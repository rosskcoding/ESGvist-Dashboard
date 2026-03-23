from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin


class RequirementItem(Base, TimestampMixin):
    __tablename__ = "requirement_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    disclosure_requirement_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("disclosure_requirements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_item_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("requirement_items.id", ondelete="CASCADE"),
        nullable=True,
    )
    item_code: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    item_type: Mapped[str] = mapped_column(String, nullable=False)  # metric|attribute|dimension|narrative|document
    value_type: Mapped[str] = mapped_column(String, nullable=False)  # number|text|boolean|date|enum|json
    unit_code: Mapped[str | None] = mapped_column(String, nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    requires_evidence: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cardinality_min: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cardinality_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    granularity_rule: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    validation_rule: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    children = relationship(
        "RequirementItem", lazy="noload", overlaps="parent",
    )
    parent = relationship(
        "RequirementItem", remote_side="RequirementItem.id", lazy="noload",
    )


class RequirementItemDependency(Base, TimestampMixin):
    __tablename__ = "requirement_item_dependencies"

    id: Mapped[int] = mapped_column(primary_key=True)
    requirement_item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("requirement_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    depends_on_item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("requirement_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    dependency_type: Mapped[str] = mapped_column(String, nullable=False)  # requires|excludes|conditional_on
    condition_expression: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "requirement_item_id", "depends_on_item_id", "dependency_type",
            name="uq_item_dependency",
        ),
    )
