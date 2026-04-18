"""add custom datasheet foundation tables

Revision ID: 20260417_01
Revises: 20260415_02
Create Date: 2026-04-17 23:40:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260417_01"
down_revision: str | None = "20260415_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return table_name in _inspector().get_table_names()


def _has_index(table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in _inspector().get_indexes(table_name))


def upgrade() -> None:
    if not _has_table("custom_datasheets"):
        op.create_table(
            "custom_datasheets",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "reporting_project_id",
                sa.Integer(),
                sa.ForeignKey("reporting_projects.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="draft"),
            sa.Column(
                "created_by",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint(
                "status in ('draft', 'active', 'archived')",
                name="chk_custom_datasheets_status",
            ),
        )
    if not _has_index("custom_datasheets", "ix_custom_datasheets_reporting_project_id"):
        op.create_index(
            "ix_custom_datasheets_reporting_project_id",
            "custom_datasheets",
            ["reporting_project_id"],
        )

    if not _has_table("custom_datasheet_items"):
        op.create_table(
            "custom_datasheet_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "custom_datasheet_id",
                sa.Integer(),
                sa.ForeignKey("custom_datasheets.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "reporting_project_id",
                sa.Integer(),
                sa.ForeignKey("reporting_projects.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "shared_element_id",
                sa.Integer(),
                sa.ForeignKey("shared_elements.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "assignment_id",
                sa.Integer(),
                sa.ForeignKey("metric_assignments.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("source_type", sa.String(), nullable=False),
            sa.Column("category", sa.String(), nullable=False),
            sa.Column("display_group", sa.String(), nullable=True),
            sa.Column("label_override", sa.String(), nullable=True),
            sa.Column("help_text", sa.Text(), nullable=True),
            sa.Column("collection_scope", sa.String(), nullable=False),
            sa.Column(
                "entity_id",
                sa.Integer(),
                sa.ForeignKey("company_entities.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "facility_id",
                sa.Integer(),
                sa.ForeignKey("company_entities.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(), nullable=False, server_default="active"),
            sa.Column(
                "created_by",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint(
                "source_type in ('framework', 'existing_custom', 'new_custom')",
                name="chk_custom_datasheet_items_source_type",
            ),
            sa.CheckConstraint(
                "category in ('environmental', 'social', 'governance', 'business_operations', 'other')",
                name="chk_custom_datasheet_items_category",
            ),
            sa.CheckConstraint(
                "collection_scope in ('project', 'entity', 'facility')",
                name="chk_custom_datasheet_items_collection_scope",
            ),
            sa.CheckConstraint(
                "status in ('active', 'archived')",
                name="chk_custom_datasheet_items_status",
            ),
        )
    for table_name, index_name, columns in (
        ("custom_datasheet_items", "ix_custom_datasheet_items_custom_datasheet_id", ["custom_datasheet_id"]),
        ("custom_datasheet_items", "ix_custom_datasheet_items_reporting_project_id", ["reporting_project_id"]),
        ("custom_datasheet_items", "ix_custom_datasheet_items_shared_element_id", ["shared_element_id"]),
        ("custom_datasheet_items", "ix_custom_datasheet_items_assignment_id", ["assignment_id"]),
        ("custom_datasheet_items", "ix_custom_datasheet_items_entity_id", ["entity_id"]),
        ("custom_datasheet_items", "ix_custom_datasheet_items_facility_id", ["facility_id"]),
    ):
        if not _has_index(table_name, index_name):
            op.create_index(index_name, table_name, columns)

    if not _has_index("custom_datasheet_items", "uq_custom_datasheet_item_context"):
        op.create_index(
            "uq_custom_datasheet_item_context",
            "custom_datasheet_items",
            [
                "custom_datasheet_id",
                "shared_element_id",
                sa.literal_column("coalesce(entity_id, 0)"),
                sa.literal_column("coalesce(facility_id, 0)"),
                "collection_scope",
            ],
            unique=True,
            postgresql_where=sa.text("status = 'active'"),
        )


def downgrade() -> None:
    if _has_table("custom_datasheet_items"):
        for index_name in (
            "uq_custom_datasheet_item_context",
            "ix_custom_datasheet_items_facility_id",
            "ix_custom_datasheet_items_entity_id",
            "ix_custom_datasheet_items_assignment_id",
            "ix_custom_datasheet_items_shared_element_id",
            "ix_custom_datasheet_items_reporting_project_id",
            "ix_custom_datasheet_items_custom_datasheet_id",
        ):
            if _has_index("custom_datasheet_items", index_name):
                op.drop_index(index_name, table_name="custom_datasheet_items")
        op.drop_table("custom_datasheet_items")

    if _has_table("custom_datasheets"):
        if _has_index("custom_datasheets", "ix_custom_datasheets_reporting_project_id"):
            op.drop_index("ix_custom_datasheets_reporting_project_id", table_name="custom_datasheets")
        op.drop_table("custom_datasheets")
