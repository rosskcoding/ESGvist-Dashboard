"""add runtime tables for form configs, calculations, support sessions, and org defaults

Revision ID: 20260324_01
Revises: None
Create Date: 2026-03-24 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260324_01"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return table_name in _inspector().get_table_names()


def _has_index(table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in _inspector().get_indexes(table_name))


def _has_column(table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in _inspector().get_columns(table_name))


def _has_check_constraint(table_name: str, constraint_name: str) -> bool:
    return any(
        constraint.get("name") == constraint_name
        for constraint in _inspector().get_check_constraints(table_name)
    )


def _ensure_index(table_name: str, index_name: str, columns: list[str]) -> None:
    if not _has_index(table_name, index_name):
        op.create_index(index_name, table_name, columns)


def _ensure_column(table_name: str, column: sa.Column) -> None:
    if not _has_column(table_name, column.name):
        op.add_column(table_name, column)


def _create_calculation_rules() -> None:
    if not _has_table("calculation_rules"):
        op.create_table(
            "calculation_rules",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("output_element_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column("formula", sa.JSON(), nullable=False),
            sa.Column("input_element_ids", sa.JSON(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["output_element_id"], ["shared_elements.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    _ensure_index("calculation_rules", op.f("ix_calculation_rules_organization_id"), ["organization_id"])
    _ensure_index("calculation_rules", op.f("ix_calculation_rules_output_element_id"), ["output_element_id"])


def _create_form_configurations() -> None:
    if not _has_table("form_configurations"):
        op.create_table(
            "form_configurations",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column("config", sa.JSON(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["project_id"], ["reporting_projects.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
    _ensure_index("form_configurations", op.f("ix_form_configurations_organization_id"), ["organization_id"])
    _ensure_index("form_configurations", op.f("ix_form_configurations_project_id"), ["project_id"])


def _create_support_sessions() -> None:
    if not _has_table("support_sessions"):
        op.create_table(
            "support_sessions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("platform_admin_id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("reason", sa.String(), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.ForeignKeyConstraint(["platform_admin_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    _ensure_index("support_sessions", op.f("ix_support_sessions_platform_admin_id"), ["platform_admin_id"])
    _ensure_index("support_sessions", op.f("ix_support_sessions_tenant_id"), ["tenant_id"])


def _upgrade_organizations() -> None:
    if not _has_table("organizations"):
        return

    _ensure_column("organizations", sa.Column("legal_name", sa.String(), nullable=True))
    _ensure_column("organizations", sa.Column("registration_number", sa.String(), nullable=True))
    _ensure_column("organizations", sa.Column("country", sa.String(), nullable=True))
    _ensure_column("organizations", sa.Column("jurisdiction", sa.String(), nullable=True))
    _ensure_column("organizations", sa.Column("industry", sa.String(), nullable=True))
    _ensure_column(
        "organizations",
        sa.Column("default_currency", sa.String(), nullable=False, server_default=sa.text("'USD'")),
    )
    _ensure_column("organizations", sa.Column("default_reporting_year", sa.Integer(), nullable=True))
    _ensure_column(
        "organizations",
        sa.Column("default_standards", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    _ensure_column("organizations", sa.Column("default_consolidation_approach", sa.String(), nullable=True))
    _ensure_column("organizations", sa.Column("default_ghg_scope_approach", sa.String(), nullable=True))
    _ensure_column(
        "organizations",
        sa.Column("allow_password_login", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    _ensure_column(
        "organizations",
        sa.Column("allow_sso_login", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    _ensure_column(
        "organizations",
        sa.Column("enforce_sso", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    _ensure_column(
        "organizations",
        sa.Column("setup_completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    _ensure_column(
        "organizations",
        sa.Column("status", sa.String(), nullable=False, server_default=sa.text("'active'")),
    )

    if op.get_bind().dialect.name != "sqlite" and not _has_check_constraint("organizations", "chk_org_status"):
        op.create_check_constraint(
            "chk_org_status",
            "organizations",
            "status IN ('active','suspended','archived')",
        )


def upgrade() -> None:
    _create_calculation_rules()
    _create_form_configurations()
    _create_support_sessions()
    _upgrade_organizations()


def downgrade() -> None:
    if _has_table("support_sessions"):
        if _has_index("support_sessions", op.f("ix_support_sessions_tenant_id")):
            op.drop_index(op.f("ix_support_sessions_tenant_id"), table_name="support_sessions")
        if _has_index("support_sessions", op.f("ix_support_sessions_platform_admin_id")):
            op.drop_index(op.f("ix_support_sessions_platform_admin_id"), table_name="support_sessions")
        op.drop_table("support_sessions")

    if _has_table("form_configurations"):
        if _has_index("form_configurations", op.f("ix_form_configurations_project_id")):
            op.drop_index(op.f("ix_form_configurations_project_id"), table_name="form_configurations")
        if _has_index("form_configurations", op.f("ix_form_configurations_organization_id")):
            op.drop_index(op.f("ix_form_configurations_organization_id"), table_name="form_configurations")
        op.drop_table("form_configurations")

    if _has_table("calculation_rules"):
        if _has_index("calculation_rules", op.f("ix_calculation_rules_output_element_id")):
            op.drop_index(op.f("ix_calculation_rules_output_element_id"), table_name="calculation_rules")
        if _has_index("calculation_rules", op.f("ix_calculation_rules_organization_id")):
            op.drop_index(op.f("ix_calculation_rules_organization_id"), table_name="calculation_rules")
        op.drop_table("calculation_rules")
