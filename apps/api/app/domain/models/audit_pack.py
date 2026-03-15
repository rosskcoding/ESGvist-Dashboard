"""
AuditPackJob model — Audit pack generation jobs.

Audit pack exports: report + evidence + comments in various formats.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Boolean
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin
from .enums import JobStatus

if TYPE_CHECKING:
    from .company import Company
    from .report import Report
    from .user import User


class AuditPackJob(Base, TimestampMixin):
    """
    AuditPackJob — Background job for generating audit pack.

    Generates:
    - Report PDF/DOCX
    - Evidence CSV
    - Comments CSV
    - Optional: Evidence summary PDF
    - ZIP bundle with attachments

    Status flow:
    - queued → running → succeeded/failed
    """

    __tablename__ = "audit_pack_jobs"

    job_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    company_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.company_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reports.report_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Job configuration
    formats: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        doc="Formats to generate: report_pdf, evidences_csv, etc.",
    )
    locales: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        doc="Locales to include",
    )
    include_internal_comments: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Include internal (team-only) comments",
    )
    evidence_statuses: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        nullable=True,
        doc="Filter evidence by statuses (null = all)",
    )
    pdf_profile: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="audit",
        doc="PDF profile: audit or screen",
    )
    # Job execution
    status: Mapped[JobStatus] = mapped_column(
        SQLEnum(
            JobStatus,
            name="job_status",
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=JobStatus.QUEUED,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    company: Mapped["Company"] = relationship(
        "Company",
        foreign_keys=[company_id],
    )
    report: Mapped["Report"] = relationship(
        "Report",
        foreign_keys=[report_id],
    )
    creator: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[created_by],
    )
    artifacts: Mapped[list["AuditPackArtifact"]] = relationship(
        "AuditPackArtifact",
        back_populates="job",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<AuditPackJob {self.job_id} {self.status.value}>"

    @property
    def is_running(self) -> bool:
        return self.status == JobStatus.RUNNING

    @property
    def is_finished(self) -> bool:
        return self.status in (JobStatus.SUCCESS, JobStatus.FAILED, JobStatus.CANCELLED)


class AuditPackArtifact(Base, TimestampMixin):
    """
    AuditPackArtifact — Generated file for audit pack.

    One artifact per format+locale combination.
    """

    __tablename__ = "audit_pack_artifacts"

    artifact_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    job_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("audit_pack_jobs.job_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    format: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Artifact format: report_pdf, evidences_csv, audit_pack_zip, etc.",
    )
    locale: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        doc="Locale for this artifact (if applicable)",
    )
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Filename for download",
    )
    path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Server path to file",
    )
    size_bytes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    sha256: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    # Warning flags (graceful degradation)
    attachments_excluded: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Whether attachments were excluded due to size limit",
    )
    warning_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Warning message if graceful fallback occurred",
    )

    # Relationship
    job: Mapped["AuditPackJob"] = relationship(
        "AuditPackJob",
        back_populates="artifacts",
    )

    def __repr__(self) -> str:
        return f"<AuditPackArtifact {self.format} for job {self.job_id}>"


