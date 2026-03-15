"""Add audit_checks table.

Revision ID: 20241227_0006
Revises: 20241227_0005
Create Date: 2024-12-27

Audit checklist: auditor marks sections/blocks/evidence as reviewed/flagged/needs_info.
Supports live review (source_snapshot_id=NULL) and snapshot-based review.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20241227_0006"
down_revision: str = "20241227_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create audit_checks table."""

    op.create_table(
        "audit_checks",
        sa.Column(
            "check_id",
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
        # Optional snapshot binding (NULL = live review)
        sa.Column(
            "source_snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("source_snapshots.snapshot_id", ondelete="SET NULL"),
            nullable=True,
            comment="NULL = live review, non-NULL = snapshot-based review",
        ),
        # Target: what is being checked
        sa.Column(
            "target_type",
            sa.String(20),
            nullable=False,
            comment="report, section, block, or evidence_item",
        ),
        sa.Column(
            "target_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        # Auditor info
        sa.Column(
            "auditor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
            nullable=False,
        ),
        # Check status
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="not_started",
        ),
        # Severity of findings (optional)
        sa.Column(
            "severity",
            sa.String(20),
            nullable=True,
            comment="critical, major, minor, info (if flagged)",
        ),
        sa.Column(
            "comment",
            sa.Text,
            nullable=True,
        ),
        sa.Column(
            "reviewed_at_utc",
            sa.DateTime(timezone=True),
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
            "target_type IN ('report', 'section', 'block', 'evidence_item')",
            name="ck_audit_checks_target_type",
        ),
        sa.CheckConstraint(
            "status IN ('not_started', 'in_review', 'reviewed', 'flagged', 'needs_info')",
            name="ck_audit_checks_status",
        ),
        sa.CheckConstraint(
            "severity IS NULL OR severity IN ('critical', 'major', 'minor', 'info')",
            name="ck_audit_checks_severity",
        ),
    )

    # Indexes
    op.create_index(
        "ix_audit_checks_report_snapshot",
        "audit_checks",
        ["report_id", "source_snapshot_id"],
    )
    op.create_index(
        "ix_audit_checks_target",
        "audit_checks",
        ["target_type", "target_id"],
    )
    op.create_index(
        "ix_audit_checks_auditor",
        "audit_checks",
        ["auditor_id"],
    )
    op.create_index(
        "ix_audit_checks_status",
        "audit_checks",
        ["status"],
    )
    op.create_index(
        "ix_audit_checks_company",
        "audit_checks",
        ["company_id"],
    )


def downgrade() -> None:
    """Drop audit_checks table."""
    op.drop_table("audit_checks")


