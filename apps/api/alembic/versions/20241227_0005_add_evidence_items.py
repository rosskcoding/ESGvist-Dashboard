"""Add evidence_items table and extend assets.

Revision ID: 20241227_0005
Revises: 20241227_0004
Create Date: 2024-12-27

Evidence storage: file/link/note attached to report/section/block with visibility control.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20241227_0005"
down_revision: str = "20241227_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create evidence_items table and extend assets with company_id."""

    # 1. Add company_id to assets (nullable first for backfill)
    op.add_column(
        "assets",
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )

    # 2. Add created_by to assets
    op.add_column(
        "assets",
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # 3. Backfill assets with default company
    default_company_id = "00000000-0000-0000-0000-000000000001"
    op.execute(f"""
        UPDATE assets
        SET company_id = '{default_company_id}'
        WHERE company_id IS NULL
    """)

    # 4. Make company_id NOT NULL and add FK
    op.alter_column("assets", "company_id", nullable=False)
    op.create_foreign_key(
        "fk_assets_company",
        "assets",
        "companies",
        ["company_id"],
        ["company_id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_assets_company", "assets", ["company_id"])

    # 5. Create evidence_items table
    op.create_table(
        "evidence_items",
        sa.Column(
            "evidence_id",
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
        # Scoped attachment: report/section/block
        sa.Column(
            "scope_type",
            sa.String(20),
            nullable=False,
            comment="report, section, or block",
        ),
        sa.Column(
            "scope_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="ID of report, section, or block",
        ),
        # Optional locale binding
        sa.Column(
            "locale",
            sa.String(10),
            nullable=True,
        ),
        # Evidence type: file, link, note
        sa.Column(
            "type",
            sa.String(10),
            nullable=False,
        ),
        sa.Column(
            "title",
            sa.String(255),
            nullable=False,
        ),
        sa.Column(
            "description",
            sa.Text,
            nullable=True,
        ),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.String),
            nullable=True,
        ),
        sa.Column(
            "source",
            sa.String(20),
            nullable=True,
            comment="internal or external",
        ),
        # Visibility control
        sa.Column(
            "visibility",
            sa.String(20),
            nullable=False,
            server_default="team",
            comment="team, audit, or restricted",
        ),
        # Type-specific payloads (mutually exclusive)
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assets.asset_id", ondelete="SET NULL"),
            nullable=True,
            comment="For file type",
        ),
        sa.Column(
            "url",
            sa.Text,
            nullable=True,
            comment="For link type",
        ),
        sa.Column(
            "note_md",
            sa.Text,
            nullable=True,
            comment="For note type (markdown)",
        ),
        # Timestamps
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
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
            "scope_type IN ('report', 'section', 'block')",
            name="ck_evidence_items_scope_type",
        ),
        sa.CheckConstraint(
            "type IN ('file', 'link', 'note')",
            name="ck_evidence_items_type",
        ),
        sa.CheckConstraint(
            "visibility IN ('team', 'audit', 'restricted')",
            name="ck_evidence_items_visibility",
        ),
        sa.CheckConstraint(
            "source IS NULL OR source IN ('internal', 'external')",
            name="ck_evidence_items_source",
        ),
        # Type-specific payload validation
        sa.CheckConstraint(
            "(type = 'file' AND asset_id IS NOT NULL AND url IS NULL AND note_md IS NULL) OR "
            "(type = 'link' AND url IS NOT NULL AND asset_id IS NULL AND note_md IS NULL) OR "
            "(type = 'note' AND note_md IS NOT NULL AND asset_id IS NULL AND url IS NULL)",
            name="ck_evidence_items_payload",
        ),
    )

    # Indexes
    op.create_index("ix_evidence_items_report", "evidence_items", ["report_id"])
    op.create_index("ix_evidence_items_scope", "evidence_items", ["scope_type", "scope_id"])
    op.create_index("ix_evidence_items_company", "evidence_items", ["company_id"])
    op.create_index("ix_evidence_items_visibility", "evidence_items", ["visibility"])


def downgrade() -> None:
    """Drop evidence_items table and remove company_id from assets."""

    op.drop_table("evidence_items")

    # Remove from assets
    op.drop_index("ix_assets_company", "assets")
    op.drop_constraint("fk_assets_company", "assets", type_="foreignkey")
    op.drop_column("assets", "created_by")
    op.drop_column("assets", "company_id")


