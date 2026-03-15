"""Add audit_pack_jobs and audit_pack_artifacts tables.

Revision ID: 20251231_1000
Revises: 20251231_0900
Create Date: 2024-12-31

Audit pack generation jobs:
- audit_pack_jobs: background jobs for generating audit packs
- audit_pack_artifacts: generated files (PDF, CSV, ZIP)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20251231_1000"
down_revision: str = "20251231_0900"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create audit_pack_jobs and audit_pack_artifacts tables."""

    # 1. Create audit_pack_jobs table
    op.create_table(
        "audit_pack_jobs",
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.company_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reports.report_id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Job configuration
        sa.Column(
            "formats",
            postgresql.ARRAY(sa.String),
            nullable=False,
            comment="Formats to generate: report_pdf, evidences_csv, etc.",
        ),
        sa.Column(
            "locales",
            postgresql.ARRAY(sa.String),
            nullable=False,
            comment="Locales to include",
        ),
        sa.Column(
            "include_internal_comments",
            sa.Boolean,
            nullable=False,
            server_default="false",
            comment="Include internal (team-only) comments",
        ),
        sa.Column(
            "evidence_statuses",
            postgresql.ARRAY(sa.String),
            nullable=True,
            comment="Filter evidence by statuses (null = all)",
        ),
        sa.Column(
            "pdf_profile",
            sa.String(20),
            nullable=False,
            server_default="audit",
            comment="PDF profile: audit or screen",
        ),
        # Job execution
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="queued",
            comment="queued, running, success, failed, cancelled",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "finished_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "error_message",
            sa.Text,
            nullable=True,
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Timestamps
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at_utc",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # Constraints
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'success', 'failed', 'cancelled', 'partial_success')",
            name="ck_audit_pack_jobs_status",
        ),
        sa.CheckConstraint(
            "pdf_profile IN ('audit', 'screen')",
            name="ck_audit_pack_jobs_pdf_profile",
        ),
    )

    # Indexes for audit_pack_jobs
    op.create_index(
        "ix_audit_pack_jobs_company",
        "audit_pack_jobs",
        ["company_id"],
    )
    op.create_index(
        "ix_audit_pack_jobs_report",
        "audit_pack_jobs",
        ["report_id"],
    )
    op.create_index(
        "ix_audit_pack_jobs_status",
        "audit_pack_jobs",
        ["status"],
    )

    # 2. Create audit_pack_artifacts table
    op.create_table(
        "audit_pack_artifacts",
        sa.Column(
            "artifact_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audit_pack_jobs.job_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "format",
            sa.String(50),
            nullable=False,
            comment="report_pdf, evidences_csv, audit_pack_zip, etc.",
        ),
        sa.Column(
            "locale",
            sa.String(10),
            nullable=True,
            comment="Locale for this artifact (if applicable)",
        ),
        sa.Column(
            "filename",
            sa.String(255),
            nullable=False,
            comment="Filename for download",
        ),
        sa.Column(
            "path",
            sa.Text,
            nullable=True,
            comment="Server path to file",
        ),
        sa.Column(
            "size_bytes",
            sa.Integer,
            nullable=True,
        ),
        sa.Column(
            "sha256",
            sa.String(64),
            nullable=True,
        ),
        # Warning flags (graceful degradation)
        sa.Column(
            "attachments_excluded",
            sa.Boolean,
            nullable=False,
            server_default="false",
            comment="Whether attachments were excluded due to size limit",
        ),
        sa.Column(
            "warning_message",
            sa.Text,
            nullable=True,
            comment="Warning message if graceful fallback occurred",
        ),
        # Timestamps
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at_utc",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Indexes for audit_pack_artifacts
    op.create_index(
        "ix_audit_pack_artifacts_job",
        "audit_pack_artifacts",
        ["job_id"],
    )


def downgrade() -> None:
    """Drop audit_pack_jobs and audit_pack_artifacts tables."""

    op.drop_table("audit_pack_artifacts")
    op.drop_table("audit_pack_jobs")


