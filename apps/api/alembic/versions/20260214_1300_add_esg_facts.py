"""Add ESG Dashboard facts table.

Revision ID: 20260214_1300
Revises: 20260214_1200
Create Date: 2026-02-14 13:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260214_1300"
down_revision: str | Sequence[str] | None = "20260214_1200"
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

    status_enum = sa.Enum(
        "draft",
        "published",
        name="esg_fact_status_enum",
        native_enum=False,
        create_constraint=True,
    )

    if not _table_exists("esg_facts"):
        op.create_table(
            "esg_facts",
            sa.Column("fact_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("metric_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("status", status_enum, nullable=False, server_default=sa.text("'draft'")),
            sa.Column("version_number", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("supersedes_fact_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("logical_key_hash", sa.String(length=64), nullable=False),
            sa.Column("period_type", sa.String(length=16), nullable=False),
            sa.Column("period_start", sa.Date(), nullable=False),
            sa.Column("period_end", sa.Date(), nullable=False),
            sa.Column("is_ytd", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("segment_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("consolidation_approach", sa.Text(), nullable=True),
            sa.Column("ghg_scope", sa.Text(), nullable=True),
            sa.Column("scope2_method", sa.Text(), nullable=True),
            sa.Column("scope3_category", sa.Text(), nullable=True),
            sa.Column("tags", postgresql.ARRAY(sa.String(length=100)), nullable=True),
            sa.Column("value_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("dataset_revision_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "quality_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "sources_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("published_at_utc", sa.DateTime(timezone=True), nullable=True),
            sa.Column("published_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["company_id"], ["companies.company_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["metric_id"], ["esg_metrics.metric_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["supersedes_fact_id"], ["esg_facts.fact_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["entity_id"], ["esg_entities.entity_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["location_id"], ["esg_locations.location_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["segment_id"], ["esg_segments.segment_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["dataset_id"], ["datasets.dataset_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["dataset_revision_id"], ["dataset_revisions.revision_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["published_by"], ["users.user_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"], ondelete="SET NULL"),
            sa.UniqueConstraint(
                "company_id",
                "logical_key_hash",
                "version_number",
                name="uq_esg_facts_company_logical_version",
            ),
            sa.CheckConstraint(
                "(value_json IS NOT NULL AND dataset_id IS NULL) OR (value_json IS NULL AND dataset_id IS NOT NULL)",
                name="ck_esg_facts_value_xor_dataset",
            ),
            sa.CheckConstraint(
                "(value_json IS NULL) OR (dataset_revision_id IS NULL)",
                name="ck_esg_facts_scalar_no_dataset_revision",
            ),
            sa.CheckConstraint("period_start <= period_end", name="ck_esg_facts_period_range"),
        )

    # Indexes may be missing if the table pre-existed (e.g., created via metadata.create_all in tests).
    for index_name, cols, unique, where in (
        (op.f("ix_esg_facts_company_id"), ["company_id"], False, None),
        (op.f("ix_esg_facts_metric_id"), ["metric_id"], False, None),
        (op.f("ix_esg_facts_supersedes_fact_id"), ["supersedes_fact_id"], False, None),
        (op.f("ix_esg_facts_logical_key_hash"), ["logical_key_hash"], False, None),
        ("ix_esg_facts_company_metric", ["company_id", "metric_id"], False, None),
        ("ix_esg_facts_company_logical_key", ["company_id", "logical_key_hash"], False, None),
        ("ix_esg_facts_company_entity", ["company_id", "entity_id"], False, None),
        ("ix_esg_facts_company_location", ["company_id", "location_id"], False, None),
        ("ix_esg_facts_company_segment", ["company_id", "segment_id"], False, None),
        ("ix_esg_facts_company_period_start", ["company_id", "period_start"], False, None),
        ("ix_esg_facts_company_period_end", ["company_id", "period_end"], False, None),
        (
            "uq_esg_facts_company_published_logical_key",
            ["company_id", "logical_key_hash"],
            True,
            sa.text("status = 'published'"),
        ),
    ):
        if not _index_exists(index_name):
            op.create_index(index_name, "esg_facts", cols, unique=unique, postgresql_where=where)


def downgrade() -> None:
    # Best-effort drop in reverse order.
    op.drop_index("uq_esg_facts_company_published_logical_key", table_name="esg_facts")
    for index_name in (
        "ix_esg_facts_company_period_end",
        "ix_esg_facts_company_period_start",
        "ix_esg_facts_company_segment",
        "ix_esg_facts_company_location",
        "ix_esg_facts_company_entity",
        "ix_esg_facts_company_logical_key",
        "ix_esg_facts_company_metric",
        op.f("ix_esg_facts_logical_key_hash"),
        op.f("ix_esg_facts_supersedes_fact_id"),
        op.f("ix_esg_facts_metric_id"),
        op.f("ix_esg_facts_company_id"),
    ):
        op.drop_index(index_name, table_name="esg_facts")
    op.drop_table("esg_facts")

