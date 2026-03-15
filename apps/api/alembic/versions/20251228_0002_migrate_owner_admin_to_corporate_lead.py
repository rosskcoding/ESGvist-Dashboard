"""Migrate is_owner/is_admin to corporate_lead RoleAssignment.

Revision ID: 20251228_0002
Revises: 20251228_0001
Create Date: 2025-12-28

This migration:
1. Creates RoleAssignment with corporate_lead role for all users with is_owner=true or is_admin=true
2. Drops is_owner and is_admin columns from company_memberships table
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20251228_0002"
down_revision: Union[str, None] = "20251228_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 0: Update role_assignments CHECK constraint to the new role set.
    # NOTE: role_assignments.role is VARCHAR + CHECK constraint (not Postgres ENUM).
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

    # Step 1: Create RoleAssignment entries for all is_owner/is_admin memberships
    op.execute(
        """
        INSERT INTO role_assignments (
            assignment_id,
            company_id,
            user_id,
            role,
            scope_type,
            scope_id,
            created_at_utc,
            created_by
        )
        SELECT
            gen_random_uuid(),
            cm.company_id,
            cm.user_id,
            'corporate_lead',
            'company',
            cm.company_id,
            COALESCE(cm.created_at_utc, NOW()),
            cm.created_by
        FROM company_memberships cm
        WHERE (cm.is_owner = true OR cm.is_admin = true)
          AND cm.is_active = true
          AND NOT EXISTS (
              SELECT 1
              FROM role_assignments ra
              WHERE ra.company_id = cm.company_id
                AND ra.user_id = cm.user_id
                AND ra.role = 'corporate_lead'
                AND ra.scope_type = 'company'
                AND ra.scope_id = cm.company_id
          )
        """
    )

    # Step 2: Drop legacy columns from company_memberships
    op.drop_column("company_memberships", "is_owner")
    op.drop_column("company_memberships", "is_admin")


def downgrade() -> None:
    # Add columns back
    op.add_column(
        "company_memberships",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "company_memberships",
        sa.Column("is_owner", sa.Boolean(), nullable=False, server_default="false"),
    )

    # Restore is_owner/is_admin flags from RoleAssignment
    op.execute(
        """
        UPDATE company_memberships cm
        SET is_owner = EXISTS (
            SELECT 1
            FROM role_assignments ra
            WHERE ra.company_id = cm.company_id
              AND ra.user_id = cm.user_id
              AND ra.role = 'corporate_lead'
              AND ra.scope_type = 'company'
              AND ra.scope_id = cm.company_id
        ),
        is_admin = EXISTS (
            SELECT 1
            FROM role_assignments ra
            WHERE ra.company_id = cm.company_id
              AND ra.user_id = cm.user_id
              AND ra.role = 'corporate_lead'
              AND ra.scope_type = 'company'
              AND ra.scope_id = cm.company_id
        )
        """
    )

    # Remove corporate_lead/content_editor assignments before restoring old CHECK constraint.
    op.execute("DELETE FROM role_assignments WHERE role IN ('corporate_lead', 'content_editor')")

    # Restore old role set in CHECK constraint (state as of 20251228_0001).
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

    # Remove server defaults
    op.alter_column("company_memberships", "is_admin", server_default=None)
    op.alter_column("company_memberships", "is_owner", server_default=None)

