"""
ReleaseBuildArtifact model — Export v2.

Tracks individual export artifacts (PDF, DOCX, print_html) for a ReleaseBuild.
Each artifact has its own status, allowing independent generation and retry.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import ArtifactErrorCode, ArtifactFormat, ArtifactStatus

if TYPE_CHECKING:
    from .release import ReleaseBuild


class ReleaseBuildArtifact(Base):
    """
    Individual export artifact for a ReleaseBuild.

    Invariants:
    - One artifact per (build_id, format, locale, profile) combination
    - Artifact can be generated independently after build completes
    - Failed artifacts can be retried without rebuilding ZIP
    """

    __tablename__ = "release_build_artifacts"
    __table_args__ = (
        # Tests create schema from SQLAlchemy models (not Alembic migrations),
        # so the uniqueness invariant must live in the model as well.
        UniqueConstraint(
            "build_id",
            "format",
            "locale",
            "profile",
            name="uq_release_build_artifacts_build_format_locale_profile",
        ),
    )

    artifact_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    build_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("release_builds.build_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    format: Mapped[ArtifactFormat] = mapped_column(
        SQLEnum(
            ArtifactFormat,
            name="artifact_format",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    locale: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        doc="Locale for this artifact (e.g. 'ru', 'en'). NULL for multi-locale artifacts.",
    )
    profile: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        doc="Profile variant (e.g. 'audit', 'screen' for PDF). NULL for default.",
    )
    status: Mapped[ArtifactStatus] = mapped_column(
        SQLEnum(
            ArtifactStatus,
            name="artifact_status",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ArtifactStatus.QUEUED,
    )
    path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Storage path to the generated artifact file.",
    )
    sha256: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        doc="SHA256 checksum of the artifact file.",
    )
    size_bytes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="File size in bytes.",
    )
    error_code: Mapped[ArtifactErrorCode] = mapped_column(
        SQLEnum(
            ArtifactErrorCode,
            name="artifact_error_code",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ArtifactErrorCode.NONE,
        doc="Structured error code for programmatic handling.",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Human-readable error message if generation failed.",
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    build: Mapped["ReleaseBuild"] = relationship(
        "ReleaseBuild",
        back_populates="artifacts",
    )

    def __repr__(self) -> str:
        return f"<ReleaseBuildArtifact {self.format.value} ({self.status.value})>"

    @property
    def is_ready(self) -> bool:
        """Check if artifact is ready for download."""
        return self.status == ArtifactStatus.DONE and self.path is not None

    @property
    def filename(self) -> str:
        """Generate a download filename for this artifact."""
        parts = ["report"]
        if self.locale:
            parts.append(self.locale)
        if self.profile:
            parts.append(self.profile)

        ext_map = {
            ArtifactFormat.ZIP: "zip",
            ArtifactFormat.PRINT_HTML: "html",
            ArtifactFormat.PDF: "pdf",
            ArtifactFormat.DOCX: "docx",
        }
        ext = ext_map.get(self.format, "bin")

        return f"{'-'.join(parts)}.{ext}"
