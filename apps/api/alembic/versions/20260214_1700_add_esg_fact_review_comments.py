"""Add ESG fact review comments table.

Revision ID: 20260214_1700
Revises: 20260214_1620
Create Date: 2026-02-14 17:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260214_1700"
down_revision: str | Sequence[str] | None = "20260214_1620"
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

    if not _table_exists("esg_fact_review_comments"):
        op.create_table(
            "esg_fact_review_comments",
            sa.Column("comment_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("logical_key_hash", sa.String(length=64), nullable=False),
            sa.Column("fact_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("body_md", sa.Text(), nullable=False),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["company_id"], ["companies.company_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["fact_id"], ["esg_facts.fact_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], ondelete="SET NULL"),
        )

    for index_name, cols in (
        (op.f("ix_esg_fact_review_comments_company_id"), ["company_id"]),
        (op.f("ix_esg_fact_review_comments_logical_key_hash"), ["logical_key_hash"]),
        (op.f("ix_esg_fact_review_comments_fact_id"), ["fact_id"]),
        ("ix_esg_fact_review_comments_company_logical", ["company_id", "logical_key_hash"]),
        ("ix_esg_fact_review_comments_company_fact", ["company_id", "fact_id"]),
    ):
        if not _index_exists(index_name):
            op.create_index(index_name, "esg_fact_review_comments", cols, unique=False)


def downgrade() -> None:
    for index_name in (
        "ix_esg_fact_review_comments_company_fact",
        "ix_esg_fact_review_comments_company_logical",
        op.f("ix_esg_fact_review_comments_fact_id"),
        op.f("ix_esg_fact_review_comments_logical_key_hash"),
        op.f("ix_esg_fact_review_comments_company_id"),
    ):
        op.drop_index(index_name, table_name="esg_fact_review_comments")
    op.drop_table("esg_fact_review_comments")

