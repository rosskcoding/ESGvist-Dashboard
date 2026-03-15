"""Allow internal_auditor role in role_assignments.

Revision ID: 20251227_0001
Revises: 20241227_0007
Create Date: 2025-12-27

Adds a new role value ("internal_auditor") to the role_assignments CHECK constraint.
The system distinguishes between internal (company) and external (third-party) audit roles.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20251227_0001"
down_revision: str = "20241227_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Extend ck_role_assignments_role to include internal_auditor."""
    op.drop_constraint("ck_role_assignments_role", "role_assignments", type_="check")
    op.create_check_constraint(
        "ck_role_assignments_role",
        "role_assignments",
        "role IN ("
        "'editor', 'reviewer', 'translator', 'exporter', 'viewer', "
        "'section_editor', 'internal_auditor', "
        "'auditor', 'audit_lead', "
        "'release_lead'"
        ")",
    )


def downgrade() -> None:
    """Revert ck_role_assignments_role to exclude internal_auditor."""
    op.drop_constraint("ck_role_assignments_role", "role_assignments", type_="check")
    op.create_check_constraint(
        "ck_role_assignments_role",
        "role_assignments",
        "role IN ("
        "'editor', 'reviewer', 'translator', 'exporter', 'viewer', "
        "'section_editor', "
        "'auditor', 'audit_lead', "
        "'release_lead'"
        ")",
    )


