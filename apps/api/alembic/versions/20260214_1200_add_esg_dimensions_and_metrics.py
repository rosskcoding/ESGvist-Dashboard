"""Add ESG Dashboard dimensions + metrics tables.

Revision ID: 20260214_1200
Revises: 20260213_2200
Create Date: 2026-02-14 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260214_1200"
down_revision: str | Sequence[str] | None = "20260213_2200"
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

    # === Dimensions ===
    for table_name, pk_name in (
        ("esg_entities", "entity_id"),
        ("esg_locations", "location_id"),
        ("esg_segments", "segment_id"),
    ):
        if not _table_exists(table_name):
            op.create_table(
                table_name,
                sa.Column(pk_name, postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
                sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
                sa.Column("code", sa.String(length=80), nullable=True),
                sa.Column("name", sa.String(length=255), nullable=False),
                sa.Column("description", sa.Text(), nullable=True),
                sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
                sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
                sa.Column(
                    "created_at_utc", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
                ),
                sa.Column(
                    "updated_at_utc", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
                ),
                sa.ForeignKeyConstraint(["company_id"], ["companies.company_id"], ondelete="CASCADE"),
                sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], ondelete="SET NULL"),
                sa.UniqueConstraint("company_id", "code", name=f"uq_{table_name}_company_code"),
            )

        # Indexes may be missing if the table pre-existed (e.g., created via metadata.create_all in tests).
        if not _index_exists(op.f(f"ix_{table_name}_company_id")):
            op.create_index(op.f(f"ix_{table_name}_company_id"), table_name, ["company_id"], unique=False)
        if not _index_exists(f"ix_{table_name}_company_name"):
            op.create_index(f"ix_{table_name}_company_name", table_name, ["company_id", "name"], unique=False)

    # === Metrics ===
    value_type_enum = sa.Enum(
        "number",
        "integer",
        "boolean",
        "string",
        "dataset",
        name="esg_metric_value_type_enum",
        native_enum=False,
        create_constraint=True,
    )

    if not _table_exists("esg_metrics"):
        op.create_table(
            "esg_metrics",
            sa.Column("metric_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("code", sa.String(length=80), nullable=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("value_type", value_type_enum, nullable=False),
            sa.Column("unit", sa.String(length=64), nullable=True),
            sa.Column(
                "value_schema_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["company_id"], ["companies.company_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"], ondelete="SET NULL"),
            sa.UniqueConstraint("company_id", "code", name="uq_esg_metrics_company_code"),
        )

    if not _index_exists(op.f("ix_esg_metrics_company_id")):
        op.create_index(op.f("ix_esg_metrics_company_id"), "esg_metrics", ["company_id"], unique=False)
    if not _index_exists("ix_esg_metrics_company_name"):
        op.create_index("ix_esg_metrics_company_name", "esg_metrics", ["company_id", "name"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_esg_metrics_company_name", table_name="esg_metrics")
    op.drop_index(op.f("ix_esg_metrics_company_id"), table_name="esg_metrics")
    op.drop_table("esg_metrics")

    for table_name in ("esg_segments", "esg_locations", "esg_entities"):
        op.drop_index(f"ix_{table_name}_company_name", table_name=table_name)
        op.drop_index(op.f(f"ix_{table_name}_company_id"), table_name=table_name)
        op.drop_table(table_name)
