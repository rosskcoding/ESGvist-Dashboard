"""
Section and SectionI18n models — SYSTEM_REGISTRY B2, B3.
"""

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Enum as SQLEnum
from sqlalchemy import ForeignKey, Index, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin
from .enums import Locale

if TYPE_CHECKING:
    from .block import Block
    from .report import Report


class Section(Base, TimestampMixin):
    """
    Section entity — TOC node inside a report.

    Invariants:
    - order_index unique within (report_id, parent_section_id)
    """

    __tablename__ = "sections"
    __table_args__ = (
        UniqueConstraint(
            "report_id",
            "parent_section_id",
            "order_index",
            name="uq_sections_order",
        ),
        CheckConstraint(
            "depth >= 0 AND depth <= 3",
            name="chk_section_depth",
        ),
        Index(
            "idx_section_structure",
            "report_id",
            "parent_section_id",
            "depth",
            "order_index",
        ),
    )

    section_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    report_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reports.report_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_section_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sections.section_id", ondelete="SET NULL"),
        nullable=True,
        doc="Optional parent for nested sections",
    )
    order_index: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
    )

    # Structure fields for table of contents
    depth: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
        doc="Nesting level 0-3 (max 4 levels)",
    )
    label_prefix: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        doc="Optional prefix before title: '1.', '09', 'A.'",
    )
    label_suffix: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Optional suffix after title: '(p. 5)'",
    )

    # Relationships
    report: Mapped["Report"] = relationship(
        "Report",
        back_populates="sections",
    )
    parent: Mapped["Section | None"] = relationship(
        "Section",
        remote_side=[section_id],
        back_populates="children",
    )
    children: Mapped[list["Section"]] = relationship(
        "Section",
        back_populates="parent",
        cascade="all, delete-orphan",
    )
    blocks: Mapped[list["Block"]] = relationship(
        "Block",
        back_populates="section",
        cascade="all, delete-orphan",
        order_by="Block.order_index",
    )
    i18n: Mapped[list["SectionI18n"]] = relationship(
        "SectionI18n",
        back_populates="section",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Section {self.section_id} (order={self.order_index})>"

    def get_i18n(self, locale: Locale | str) -> "SectionI18n | None":
        """Get localized content for a specific locale."""
        locale_value = locale.value if isinstance(locale, Locale) else locale
        for item in self.i18n:
            if item.locale.value == locale_value:
                return item
        return None


class SectionI18n(Base):
    """
    Localized section fields per locale.

    Invariants:
    - (section_id, locale) unique
    - slug unique within (report_id, locale) — enforced at app level
    """

    __tablename__ = "section_i18n"
    __table_args__ = (UniqueConstraint("section_id", "locale", name="uq_section_i18n_locale"),)

    section_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sections.section_id", ondelete="CASCADE"),
        primary_key=True,
    )
    locale: Mapped[Locale] = mapped_column(
        SQLEnum(Locale, name="locale", create_type=False, values_callable=lambda x: [e.value for e in x]),
        primary_key=True,
    )
    title: Mapped[str] = mapped_column(
        String(240),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    section: Mapped["Section"] = relationship(
        "Section",
        back_populates="i18n",
    )

    def __repr__(self) -> str:
        return f"<SectionI18n {self.locale.value}: {self.title}>"


