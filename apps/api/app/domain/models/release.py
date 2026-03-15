"""
SourceSnapshot and ReleaseBuild models — SYSTEM_REGISTRY B7, B8.

Extended for audit soft-gate:
- audit_basis: snapshot or live
- audit_summary: coverage, issues counts
- release_rationale: required if critical issues
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import AuditBasis, BuildScope, BuildStatus, BuildType, PackageMode

if TYPE_CHECKING:
    from .artifact import ReleaseBuildArtifact
    from .report import Report
    from .user import User


class SourceSnapshot(Base):
    """
    Immutable pointer used as input for deterministic builds.

    Invariants:
    - Snapshot is immutable; never updated after creation
    """

    __tablename__ = "source_snapshots"

    snapshot_id: Mapped[UUID] = mapped_column(
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
    content_root_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="SHA256 hash of content tree",
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # Relationships
    report: Mapped["Report"] = relationship(
        "Report",
        back_populates="snapshots",
    )
    builds: Mapped[list["ReleaseBuild"]] = relationship(
        "ReleaseBuild",
        back_populates="snapshot",
    )

    def __repr__(self) -> str:
        return f"<SourceSnapshot {self.snapshot_id}>"


class ReleaseBuild(Base):
    """
    Immutable static export build record (ZIP + manifest + checksums).

    Invariants:
    - ReleaseBuild(build_type=release) MUST satisfy export gating rules
    """

    __tablename__ = "release_builds"

    build_id: Mapped[UUID] = mapped_column(
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
    build_type: Mapped[BuildType] = mapped_column(
        SQLEnum(BuildType, name="build_type", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    status: Mapped[BuildStatus] = mapped_column(
        SQLEnum(BuildStatus, name="build_status", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=BuildStatus.QUEUED,
    )
    source_snapshot_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("source_snapshots.snapshot_id"),
        nullable=True,
    )
    theme_slug: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    base_path: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        default="/",
    )
    locales: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
    )
    package_mode: Mapped[PackageMode] = mapped_column(
        SQLEnum(
            PackageMode,
            name="package_mode",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=PackageMode.PORTABLE,
        doc="Export package mode: portable (no JS) or interactive (with JS/search)",
    )
    scope: Mapped[BuildScope] = mapped_column(
        SQLEnum(
            BuildScope,
            name="build_scope",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=BuildScope.FULL,
        doc="Build scope: full report, single section, or single block",
    )
    target_section_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sections.section_id", ondelete="SET NULL"),
        nullable=True,
        doc="Target section for SECTION scope exports",
    )
    target_block_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("blocks.block_id", ondelete="SET NULL"),
        nullable=True,
        doc="Target block for BLOCK scope exports",
    )
    zip_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    zip_sha256: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    manifest_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    finished_at_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    # Audit soft-gate fields
    audit_basis: Mapped[AuditBasis] = mapped_column(
        SQLEnum(
            AuditBasis,
            name="audit_basis_enum",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=AuditBasis.SNAPSHOT,
        doc="Basis for audit summary: snapshot or live",
    )
    audit_summary: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="Coverage, issues counts, evidence completeness at release time",
    )
    ack_audit_summary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="User acknowledged audit summary before release",
    )
    release_rationale: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Required if critical issues exist at release time",
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    # Export v2: build options (targets, pdf_profile, etc.)
    build_options: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        doc="Build options: targets, pdf_profile, include_toc, etc.",
    )
    # Idempotency and retry tracking
    idempotency_key: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        doc="Idempotency key for deduplication (hash of build params)",
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Number of retry attempts for this build",
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        doc="Maximum retry attempts allowed",
    )

    # Relationships
    report: Mapped["Report"] = relationship(
        "Report",
        back_populates="builds",
    )
    snapshot: Mapped["SourceSnapshot | None"] = relationship(
        "SourceSnapshot",
        back_populates="builds",
    )
    creator: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[created_by],
    )
    artifacts: Mapped[list["ReleaseBuildArtifact"]] = relationship(
        "ReleaseBuildArtifact",
        back_populates="build",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<ReleaseBuild {self.build_type.value} ({self.status.value})>"

    @property
    def include_js(self) -> bool:
        """Whether to include JavaScript in the export."""
        return self.package_mode == PackageMode.INTERACTIVE

    @property
    def include_search(self) -> bool:
        """Whether to include search functionality in the export."""
        return self.package_mode == PackageMode.INTERACTIVE

    @property
    def can_retry(self) -> bool:
        """Check if build can be retried based on retry_count."""
        return self.retry_count < self.max_retries

    def increment_retry(self) -> None:
        """Increment retry counter (call before retry attempt)."""
        self.retry_count += 1

    def compute_idempotency_key(self) -> str:
        """
        Compute idempotency key for build deduplication.

        Key includes: report_id, build_type, locales, theme, scope, package_mode.
        Excludes: timestamps, status, error_message (transient state).

        Returns:
            SHA256 hash (first 16 chars) of canonical build params
        """
        import hashlib
        import json

        params = {
            "report_id": str(self.report_id),
            "build_type": self.build_type.value,
            "locales": sorted(self.locales),
            "theme_slug": self.theme_slug,
            "scope": self.scope.value,
            "package_mode": self.package_mode.value,
            "target_section_id": str(self.target_section_id) if self.target_section_id else None,
            "target_block_id": str(self.target_block_id) if self.target_block_id else None,
        }
        canonical = json.dumps(params, sort_keys=True, separators=(",", ":"))
        full_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return full_hash[:16]  # 16 chars sufficient for deduplication

    @property
    def has_critical_issues(self) -> bool:
        """Check if audit summary has critical issues."""
        if not self.audit_summary:
            return False
        return self.audit_summary.get("critical_count", 0) > 0

    @property
    def requires_rationale(self) -> bool:
        """Check if release requires rationale (critical issues present)."""
        return self.has_critical_issues and not self.release_rationale

    @property
    def targets(self) -> list[str]:
        """Get requested export targets from build_options."""
        # Default: always build ZIP + include print bundle inside ZIP (so PDF/DOCX can be generated on-demand).
        default_targets = ["zip", "print_html"]
        if not self.build_options:
            return default_targets
        targets = self.build_options.get("targets")
        return targets or default_targets

    @property
    def needs_print_bundle(self) -> bool:
        """Check if print bundle should be generated (pdf or docx in targets)."""
        targets = self.targets
        return "print_html" in targets or "pdf" in targets or "docx" in targets

    def get_option(self, key: str, default: any = None) -> any:
        """Get a build option value."""
        if not self.build_options:
            return default
        return self.build_options.get(key, default)

    def set_audit_summary(
        self,
        coverage: float,
        reviewed_count: int,
        total_count: int,
        critical_count: int = 0,
        major_count: int = 0,
        minor_count: int = 0,
        info_count: int = 0,
    ) -> None:
        """Set audit summary data."""
        self.audit_summary = {
            "coverage": coverage,
            "reviewed_count": reviewed_count,
            "total_count": total_count,
            "critical_count": critical_count,
            "major_count": major_count,
            "minor_count": minor_count,
            "info_count": info_count,
        }
