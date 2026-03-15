"""Add content_versions table for lightweight change tracking.

Revision ID: 20251231_0900
Revises: 20251231_0800
Create Date: 2024-12-31

Content versions for audit trail:
- Stores last 3 versions of block content per locale
- Transactional retention (no cron needed)
- Triggered on BlockI18n.fields_json updates
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20251231_0900"
down_revision: str = "20251231_0800"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create content_versions table."""

    op.create_table(
        "content_versions",
        sa.Column(
            "version_id",
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
        sa.Column(
            "block_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("blocks.block_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "locale",
            sa.String(10),
            nullable=False,
            comment="Locale of the content version",
        ),
        sa.Column(
            "saved_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "saved_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "fields_json_snapshot",
            postgresql.JSONB,
            nullable=False,
            comment="Snapshot of BlockI18n.fields_json at this point",
        ),
    )

    # Indexes for efficient queries
    op.create_index(
        "ix_content_versions_block_locale",
        "content_versions",
        ["block_id", "locale", "saved_at"],
        postgresql_ops={"saved_at": "DESC"},
    )
    op.create_index(
        "ix_content_versions_company",
        "content_versions",
        ["company_id"],
    )
    op.create_index(
        "ix_content_versions_report",
        "content_versions",
        ["report_id"],
    )


def downgrade() -> None:
    """Drop content_versions table."""

    op.drop_table("content_versions")


