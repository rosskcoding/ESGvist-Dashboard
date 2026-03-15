"""Add ESG fact evidence items table.

Revision ID: 20260214_1400
Revises: 20260214_1300
Create Date: 2026-02-14 14:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260214_1400"
down_revision: str | Sequence[str] | None = "20260214_1300"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    def _table_exists(name: str) -> bool:
        return (
            bind.execute(
                sa.text(
                    """
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = current_schema()
                      AND table_name = :name
                    LIMIT 1
                    """
                ),
                {"name": name},
            ).scalar()
            is not None
        )

    def _index_exists(name: str) -> bool:
        return (
            bind.execute(
                sa.text(
                    """
                    SELECT 1
                    FROM pg_indexes
                    WHERE schemaname = current_schema()
                      AND indexname = :name
                    LIMIT 1
                    """
                ),
                {"name": name},
            ).scalar()
            is not None
        )

    evidence_type_enum = sa.Enum(
        "file",
        "link",
        "note",
        name="esg_fact_evidence_type_enum",
        native_enum=False,
        create_constraint=True,
    )

    if not _table_exists("esg_fact_evidence_items"):
        op.create_table(
            "esg_fact_evidence_items",
            sa.Column("evidence_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("fact_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("type", evidence_type_enum, nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("url", sa.Text(), nullable=True),
            sa.Column("note_md", sa.Text(), nullable=True),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["company_id"], ["companies.company_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["fact_id"], ["esg_facts.fact_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["asset_id"], ["assets.asset_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], ondelete="SET NULL"),
            sa.CheckConstraint(
                "("
                "type = 'file' AND asset_id IS NOT NULL AND url IS NULL AND note_md IS NULL"
                ") OR ("
                "type = 'link' AND url IS NOT NULL AND asset_id IS NULL AND note_md IS NULL"
                ") OR ("
                "type = 'note' AND note_md IS NOT NULL AND asset_id IS NULL AND url IS NULL"
                ")",
                name="ck_esg_fact_evidence_type_payload",
            ),
        )

    # Indexes may be missing if the table pre-existed (e.g., created via metadata.create_all in tests).
    for index_name, cols in (
        (op.f("ix_esg_fact_evidence_items_company_id"), ["company_id"]),
        (op.f("ix_esg_fact_evidence_items_fact_id"), ["fact_id"]),
        ("ix_esg_fact_evidence_company_fact", ["company_id", "fact_id"]),
    ):
        if not _index_exists(index_name):
            op.create_index(index_name, "esg_fact_evidence_items", cols, unique=False)


def downgrade() -> None:
    for index_name in (
        "ix_esg_fact_evidence_company_fact",
        op.f("ix_esg_fact_evidence_items_fact_id"),
        op.f("ix_esg_fact_evidence_items_company_id"),
    ):
        op.drop_index(index_name, table_name="esg_fact_evidence_items")
    op.drop_table("esg_fact_evidence_items")

