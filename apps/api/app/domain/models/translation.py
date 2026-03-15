"""
Translation models — SYSTEM_REGISTRY B9, B10, B11.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, SmallInteger, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin
from .enums import GlossaryStrictness, JobStatus, Locale, TranslationStatus

if TYPE_CHECKING:
    from .block import Block
    from .report import Report


class GlossaryTerm(Base, TimestampMixin):
    """
    RU/EN/KK mapping with strictness behavior for translation.

    Strictness levels:
    - do_not_translate: Keep original, wrap in {{DNT:...}}
    - strict: Must use exact translation
    - preferred: Suggest but allow alternatives
    """

    __tablename__ = "glossary_terms"

    term_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    ru: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    en: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    kk: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    strictness: Mapped[GlossaryStrictness] = mapped_column(
        SQLEnum(GlossaryStrictness, name="glossary_strictness", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=GlossaryStrictness.PREFERRED,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<GlossaryTerm {self.ru} ({self.strictness.value})>"

    def get_translation(self, locale: Locale | str) -> str | None:
        """Get translation for a specific locale.

        Note: GlossaryTerm currently stores translations in fixed columns (ru/en/kk).
        For other locales, return None so callers can skip terms instead of falling back
        to an unrelated language.
        """
        locale_value = locale.value if isinstance(locale, Locale) else locale
        if locale_value not in ("ru", "en", "kk"):
            return None
        return getattr(self, locale_value, None)


class TranslationJob(Base):
    """
    Queued translation job spanning a scope.

    Invariants:
    - Partial success is allowed; successful TUs are persisted
    """

    __tablename__ = "translation_jobs"

    job_id: Mapped[UUID] = mapped_column(
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
    scope_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Scope: report, section, blocks",
    )
    scope_ids: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        doc="IDs within scope",
    )
    source_locale: Mapped[Locale] = mapped_column(
        SQLEnum(Locale, name="locale", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    target_locales: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
    )
    mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="reporting",
        doc="Mode: reporting, marketing",
    )
    status: Mapped[JobStatus] = mapped_column(
        SQLEnum(JobStatus, name="job_status", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=JobStatus.QUEUED,
    )
    progress: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    error_log: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    started_at_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # Relationships
    report: Mapped["Report"] = relationship(
        "Report",
        back_populates="translation_jobs",
    )

    def __repr__(self) -> str:
        return f"<TranslationJob {self.job_id} ({self.status.value})>"


class TranslationUnit(Base, TimestampMixin):
    """
    Chunk translation record with caching by source_hash.

    Invariants:
    - chunk_id == "{block_id}:{field_name}:{chunk_index}"
    - If placeholders mismatch → qa_required
    """

    __tablename__ = "translation_units"

    tu_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    chunk_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
        doc="Canonical: {block_id}:{field_name}:{chunk_index}",
    )
    block_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("blocks.block_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
    )
    source_locale: Mapped[Locale] = mapped_column(
        SQLEnum(Locale, name="locale", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    target_locale: Mapped[Locale] = mapped_column(
        SQLEnum(Locale, name="locale", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    source_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    target_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    source_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        doc="Hash of source_text + glossary_version + prompt_version + mode",
    )
    status: Mapped[TranslationStatus] = mapped_column(
        SQLEnum(TranslationStatus, name="translation_status", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=TranslationStatus.PENDING,
    )
    qa_flags: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=list,
    )
    placeholders_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="Extracted placeholders for validation",
    )

    # Relationships
    block: Mapped["Block"] = relationship(
        "Block",
        back_populates="translation_units",
    )

    def __repr__(self) -> str:
        return f"<TranslationUnit {self.chunk_id} ({self.status.value})>"

    @classmethod
    def make_chunk_id(cls, block_id: UUID, field_name: str, chunk_index: int) -> str:
        """Create canonical chunk_id."""
        return f"{block_id}:{field_name}:{chunk_index}"
