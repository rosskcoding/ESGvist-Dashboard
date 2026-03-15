"""Add translator role to role_assignments CHECK constraint.

Revision ID: 20260214_1500
Revises: 20260214_1400
Create Date: 2026-02-14 15:00:00

The application supports the TRANSLATOR role (RBAC + translation workflows),
but the DB-level CHECK constraint on role_assignments.role must allow it.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260214_1500"
down_revision: str | Sequence[str] | None = "20260214_1400"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_role_assignments_role", "role_assignments", type_="check")
    op.create_check_constraint(
        "ck_role_assignments_role",
        "role_assignments",
        "role IN ("
        "'corporate_lead', "
        "'editor', 'content_editor', 'viewer', 'section_editor', "
        "'translator', "
        "'internal_auditor', 'auditor', 'audit_lead'"
        ")",
    )


def downgrade() -> None:
    op.drop_constraint("ck_role_assignments_role", "role_assignments", type_="check")
    op.create_check_constraint(
        "ck_role_assignments_role",
        "role_assignments",
        "role IN ("
        "'corporate_lead', "
        "'editor', 'content_editor', 'viewer', 'section_editor', "
        "'internal_auditor', 'auditor', 'audit_lead'"
        ")",
    )

