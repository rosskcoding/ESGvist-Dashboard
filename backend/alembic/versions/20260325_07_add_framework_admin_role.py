"""allow framework_admin as platform-scoped role

Revision ID: 20260325_07
Revises: 20260325_06
Create Date: 2026-03-25 23:55:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260325_07"
down_revision: str | None = "b8cf0807fad2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return table_name in _inspector().get_table_names()


def _has_check_constraint(table_name: str, constraint_name: str) -> bool:
    inspector = _inspector()
    return any(
        constraint.get("name") == constraint_name
        for constraint in inspector.get_check_constraints(table_name)
    )


def upgrade() -> None:
    if not _has_table("role_bindings"):
        return

    with op.batch_alter_table("role_bindings") as batch_op:
        if _has_check_constraint("role_bindings", "chk_platform_role"):
            batch_op.drop_constraint("chk_platform_role", type_="check")
        if _has_check_constraint("role_bindings", "chk_role_enum"):
            batch_op.drop_constraint("chk_role_enum", type_="check")

        batch_op.create_check_constraint(
            "chk_platform_role",
            "(scope_type = 'platform' AND role IN ('platform_admin', 'framework_admin')) OR "
            "(scope_type = 'organization' AND role NOT IN ('platform_admin', 'framework_admin'))",
        )
        batch_op.create_check_constraint(
            "chk_role_enum",
            "role IN ('platform_admin', 'framework_admin', 'admin', 'esg_manager', 'reviewer', 'collector', 'auditor')",
        )


def downgrade() -> None:
    if not _has_table("role_bindings"):
        return

    with op.batch_alter_table("role_bindings") as batch_op:
        if _has_check_constraint("role_bindings", "chk_platform_role"):
            batch_op.drop_constraint("chk_platform_role", type_="check")
        if _has_check_constraint("role_bindings", "chk_role_enum"):
            batch_op.drop_constraint("chk_role_enum", type_="check")

        batch_op.create_check_constraint(
            "chk_platform_role",
            "(scope_type = 'platform' AND role = 'platform_admin') OR "
            "(scope_type = 'organization' AND role != 'platform_admin')",
        )
        batch_op.create_check_constraint(
            "chk_role_enum",
            "role IN ('platform_admin', 'admin', 'esg_manager', 'reviewer', 'collector', 'auditor')",
        )
