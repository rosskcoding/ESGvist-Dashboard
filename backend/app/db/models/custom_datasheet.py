from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, TimestampMixin


class CustomDatasheet(Base, TimestampMixin):
    __tablename__ = "custom_datasheets"

    id: Mapped[int] = mapped_column(primary_key=True)
    reporting_project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("reporting_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default="draft", nullable=False)
    created_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "status in ('draft', 'active', 'archived')",
            name="chk_custom_datasheets_status",
        ),
    )


class CustomDatasheetItem(Base, TimestampMixin):
    __tablename__ = "custom_datasheet_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    custom_datasheet_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("custom_datasheets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reporting_project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("reporting_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    shared_element_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("shared_elements.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    assignment_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("metric_assignments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    display_group: Mapped[str | None] = mapped_column(String, nullable=True)
    label_override: Mapped[str | None] = mapped_column(String, nullable=True)
    help_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    collection_scope: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("company_entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    facility_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("company_entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)
    created_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "source_type in ('framework', 'existing_custom', 'new_custom')",
            name="chk_custom_datasheet_items_source_type",
        ),
        CheckConstraint(
            "category in ('environmental', 'social', 'governance', 'business_operations', 'other')",
            name="chk_custom_datasheet_items_category",
        ),
        CheckConstraint(
            "collection_scope in ('project', 'entity', 'facility')",
            name="chk_custom_datasheet_items_collection_scope",
        ),
        CheckConstraint(
            "status in ('active', 'archived')",
            name="chk_custom_datasheet_items_status",
        ),
    )
