"""
Report model — SYSTEM_REGISTRY B1.

Extended for multi-tenant:
- company_id: tenant binding
- structure_status: freeze/unfreeze structure
"""

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from .base import Base, TimestampMixin
from .enums import Locale, StructureStatus

if TYPE_CHECKING:
    from .checkpoint import ReportCheckpoint
    from .company import Company
    from .release import ReleaseBuild, SourceSnapshot
    from .section import Section
    from .translation import TranslationJob


class Report(Base, TimestampMixin):
    """
    Report entity — root container for annual/ESG report.

    Invariants (from SYSTEM_REGISTRY):
    - source_locale ∈ enabled_locales
    - default_locale ∈ enabled_locales
    - release_locales ⊆ enabled_locales
    - company_id is required (tenant binding)

    Structure status:
    - draft: structure can be modified
    - frozen: structure locked, only content edits allowed
    """

    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint("year >= 2000 AND year <= 2100", name="ck_reports_year_range"),
    )

    report_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    # Tenant binding
    company_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.company_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    year: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    source_locale: Mapped[Locale] = mapped_column(
        SQLEnum(Locale, name="locale", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=Locale.RU,
        doc="Canonical source-of-truth language for translation",
    )
    default_locale: Mapped[Locale] = mapped_column(
        SQLEnum(Locale, name="locale", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=Locale.RU,
        doc="UI default language for editing/preview",
    )
    enabled_locales: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=["ru"],
        doc="Locales available in authoring",
    )
    release_locales: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=["ru"],
        doc="Locales included in release build gating",
    )
    theme_slug: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="default",
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        doc="URL-friendly identifier, e.g. '2025-kap'",
    )
    design_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        doc="Design settings: layout, typography, presets, overrides",
    )
    # Structure freeze status
    structure_status: Mapped[StructureStatus] = mapped_column(
        SQLEnum(
            StructureStatus,
            name="structure_status_enum",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=StructureStatus.DRAFT,
        doc="draft = structure editable, frozen = only content edits",
    )

    # Relationships
    company: Mapped["Company"] = relationship(
        "Company",
        back_populates="reports",
    )
    sections: Mapped[list["Section"]] = relationship(
        "Section",
        back_populates="report",
        cascade="all, delete-orphan",
        order_by="Section.order_index",
    )
    builds: Mapped[list["ReleaseBuild"]] = relationship(
        "ReleaseBuild",
        back_populates="report",
        cascade="all, delete-orphan",
    )
    snapshots: Mapped[list["SourceSnapshot"]] = relationship(
        "SourceSnapshot",
        back_populates="report",
        cascade="all, delete-orphan",
    )
    translation_jobs: Mapped[list["TranslationJob"]] = relationship(
        "TranslationJob",
        back_populates="report",
        cascade="all, delete-orphan",
    )
    checkpoints: Mapped[list["ReportCheckpoint"]] = relationship(
        "ReportCheckpoint",
        back_populates="report",
        cascade="all, delete-orphan",
        order_by="ReportCheckpoint.created_at_utc.desc()",
    )

    def __repr__(self) -> str:
        return f"<Report {self.year}: {self.title}>"

    @validates("source_locale")
    def validate_source_locale(self, _key: str, value: Locale) -> Locale:
        """Validate source_locale ∈ enabled_locales."""
        if self.enabled_locales and value.value not in self.enabled_locales:
            raise ValueError(f"source_locale '{value}' must be in enabled_locales")
        return value

    @validates("default_locale")
    def validate_default_locale(self, _key: str, value: Locale) -> Locale:
        """Validate default_locale ∈ enabled_locales."""
        if self.enabled_locales and value.value not in self.enabled_locales:
            raise ValueError(f"default_locale '{value}' must be in enabled_locales")
        return value

    @validates("release_locales")
    def validate_release_locales(self, _key: str, value: list[str]) -> list[str]:
        """Validate release_locales ⊆ enabled_locales."""
        if self.enabled_locales:
            invalid = set(value) - set(self.enabled_locales)
            if invalid:
                raise ValueError(f"release_locales {invalid} must be subset of enabled_locales")
        return value

    @property
    def is_structure_frozen(self) -> bool:
        """Check if structure is frozen (no structural changes allowed)."""
        return self.structure_status == StructureStatus.FROZEN

    @property
    def is_structure_draft(self) -> bool:
        """Check if structure is in draft mode (changes allowed)."""
        return self.structure_status == StructureStatus.DRAFT

    def freeze_structure(self) -> None:
        """Freeze report structure."""
        self.structure_status = StructureStatus.FROZEN

    def unfreeze_structure(self) -> None:
        """Unfreeze report structure (requires audit log with reason)."""
        self.structure_status = StructureStatus.DRAFT
