"""
Block and BlockI18n models — SYSTEM_REGISTRY B4, B5.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin
from .enums import BlockType, BlockVariant, ContentStatus, Locale

if TYPE_CHECKING:
    from .asset import AssetLink
    from .report import Report
    from .section import Section
    from .translation import TranslationUnit
    from .user import User


class Block(Base, TimestampMixin):
    """
    Block entity — atomic content unit.

    Invariants:
    - Localized text MUST NOT be stored in data_json (Section F.3)
    - version increments on each write
    - If custom_override_enabled=true then CUSTOM ∈ qa_flags_global
    """

    __tablename__ = "blocks"

    block_id: Mapped[UUID] = mapped_column(
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
    section_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sections.section_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[BlockType] = mapped_column(
        SQLEnum(BlockType, name="block_type", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    variant: Mapped[BlockVariant] = mapped_column(
        SQLEnum(BlockVariant, name="block_variant", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=BlockVariant.DEFAULT,
    )
    order_index: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
    )
    data_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        doc="NON-localized schema-bound data (structure, layout)",
    )
    qa_flags_global: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=list,
        doc="Global QA flags: CUSTOM, DATA_PENDING, STRUCTURE_CHANGED",
    )
    custom_override_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        doc="Optimistic locking version",
    )
    owner_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    report: Mapped["Report"] = relationship("Report")
    section: Mapped["Section"] = relationship(
        "Section",
        back_populates="blocks",
    )
    owner: Mapped["User | None"] = relationship(
        "User",
        back_populates="owned_blocks",
        foreign_keys=[owner_user_id],
    )
    i18n: Mapped[list["BlockI18n"]] = relationship(
        "BlockI18n",
        back_populates="block",
        cascade="all, delete-orphan",
    )
    asset_links: Mapped[list["AssetLink"]] = relationship(
        "AssetLink",
        back_populates="block",
        cascade="all, delete-orphan",
    )
    translation_units: Mapped[list["TranslationUnit"]] = relationship(
        "TranslationUnit",
        back_populates="block",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Block {self.type.value} ({self.block_id})>"

    def get_i18n(self, locale: Locale | str) -> "BlockI18n | None":
        """Get localized content for a specific locale."""
        locale_value = locale.value if isinstance(locale, Locale) else locale
        for item in self.i18n:
            if item.locale.value == locale_value:
                return item
        return None

    def increment_version(self) -> None:
        """Increment version for optimistic locking."""
        self.version += 1


class BlockI18n(Base):
    """
    Localized block fields per locale.

    Invariants:
    - (block_id, locale) unique
    - status is per-locale workflow state
    """

    __tablename__ = "block_i18n"
    __table_args__ = (UniqueConstraint("block_id", "locale", name="uq_block_i18n_locale"),)

    block_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("blocks.block_id", ondelete="CASCADE"),
        primary_key=True,
    )
    locale: Mapped[Locale] = mapped_column(
        SQLEnum(Locale, name="locale", create_type=False, values_callable=lambda x: [e.value for e in x]),
        primary_key=True,
    )
    status: Mapped[ContentStatus] = mapped_column(
        SQLEnum(ContentStatus, name="content_status", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ContentStatus.DRAFT,
    )
    qa_flags_by_locale: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=list,
        doc="Locale-specific QA flags: PLACEHOLDER_MISMATCH, NEEDS_RETRANSLATE",
    )
    fields_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        doc="Localized fields (body_html, caption, alt_text, etc.)",
    )
    custom_html_sanitized: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Sanitized custom HTML override",
    )
    custom_css_validated: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Validated custom CSS (scoped)",
    )
    last_approved_at_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    block: Mapped["Block"] = relationship(
        "Block",
        back_populates="i18n",
    )

    def __repr__(self) -> str:
        return f"<BlockI18n {self.locale.value}: {self.status.value}>"

    def can_transition_to(self, new_status: ContentStatus) -> bool:
        """Check if status transition is allowed."""
        allowed_transitions = {
            ContentStatus.DRAFT: {ContentStatus.READY},
            ContentStatus.READY: {ContentStatus.QA_REQUIRED},
            ContentStatus.QA_REQUIRED: {ContentStatus.APPROVED},
            ContentStatus.APPROVED: {ContentStatus.DRAFT},  # Rollback
        }
        return new_status in allowed_transitions.get(self.status, set())



