"""Extend release_builds with audit summary and audit_events with company_id.

Revision ID: 20241227_0007
Revises: 20241227_0006
Create Date: 2024-12-27

Soft-gate release: audit_summary, ack_audit_summary, release_rationale.
Audit log: company_id for tenant-scoped event filtering.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20241227_0007"
down_revision: str = "20241227_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Extend release_builds and audit_events."""

    # 1. Add audit-related columns to release_builds
    op.add_column(
        "release_builds",
        sa.Column(
            "audit_basis",
            sa.String(20),
            nullable=False,
            server_default="snapshot",
            comment="snapshot or live - basis for audit summary",
        ),
    )
    op.add_column(
        "release_builds",
        sa.Column(
            "audit_summary",
            postgresql.JSONB,
            nullable=True,
            comment="Coverage, issues counts, evidence completeness at release time",
        ),
    )
    op.add_column(
        "release_builds",
        sa.Column(
            "ack_audit_summary",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
            comment="User acknowledged audit summary before release",
        ),
    )
    op.add_column(
        "release_builds",
        sa.Column(
            "release_rationale",
            sa.Text,
            nullable=True,
            comment="Required if critical issues exist at release time",
        ),
    )
    op.add_column(
        "release_builds",
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # Add check constraint for audit_basis
    op.create_check_constraint(
        "ck_release_builds_audit_basis",
        "release_builds",
        "audit_basis IN ('snapshot', 'live')",
    )

    # 2. Add company_id to audit_events (nullable for platform-level events)
    op.add_column(
        "audit_events",
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.company_id", ondelete="SET NULL"),
            nullable=True,
            comment="Tenant scope for event filtering, NULL for platform events",
        ),
    )

    # Index for company-scoped audit log queries
    op.create_index(
        "ix_audit_events_company_time",
        "audit_events",
        ["company_id", "timestamp_utc"],
    )

    # 3. Backfill existing audit_events with default company
    default_company_id = "00000000-0000-0000-0000-000000000001"
    op.execute(f"""
        UPDATE audit_events
        SET company_id = '{default_company_id}'
        WHERE company_id IS NULL
    """)


def downgrade() -> None:
    """Remove audit extensions from release_builds and audit_events."""

    # Remove from audit_events
    op.drop_index("ix_audit_events_company_time", "audit_events")
    op.drop_column("audit_events", "company_id")

    # Remove from release_builds
    op.drop_constraint("ck_release_builds_audit_basis", "release_builds", type_="check")
    op.drop_column("release_builds", "created_by")
    op.drop_column("release_builds", "release_rationale")
    op.drop_column("release_builds", "ack_audit_summary")
    op.drop_column("release_builds", "audit_summary")
    op.drop_column("release_builds", "audit_basis")


