"""Add role_assignments table.

Revision ID: 20241227_0003
Revises: 20241227_0002
Create Date: 2024-12-27

Unified scoped role assignments: editor, reviewer, translator, exporter, viewer,
section_editor, auditor, audit_lead, release_lead with scope_type/scope_id.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20241227_0003"
down_revision: str = "20241227_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create role_assignments table."""

    op.create_table(
        "role_assignments",
        sa.Column(
            "assignment_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.company_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.String(30),
            nullable=False,
        ),
        sa.Column(
            "scope_type",
            sa.String(20),
            nullable=False,
        ),
        sa.Column(
            "scope_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "locales",
            postgresql.ARRAY(sa.String),
            nullable=True,
            comment="Locale restrictions for translator role",
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "role IN ('editor', 'reviewer', 'translator', 'exporter', 'viewer', "
            "'section_editor', 'auditor', 'audit_lead', 'release_lead')",
            name="ck_role_assignments_role",
        ),
        sa.CheckConstraint(
            "scope_type IN ('company', 'report', 'section')",
            name="ck_role_assignments_scope_type",
        ),
    )

    # Indexes for common lookups
    op.create_index(
        "ix_role_assignments_company_user",
        "role_assignments",
        ["company_id", "user_id"],
    )
    op.create_index(
        "ix_role_assignments_scope",
        "role_assignments",
        ["scope_type", "scope_id"],
    )
    op.create_index(
        "ix_role_assignments_role",
        "role_assignments",
        ["role"],
    )
    op.create_index(
        "ix_role_assignments_user",
        "role_assignments",
        ["user_id"],
    )

    # Migrate existing users.role to role_assignments
    # Map old role -> new role with company scope
    default_company_id = "00000000-0000-0000-0000-000000000001"

    # Create role assignments for existing users (except admin who are handled via is_superuser)
    op.execute(f"""
        INSERT INTO role_assignments (
            assignment_id, company_id, user_id, role, scope_type, scope_id,
            locales, created_at_utc
        )
        SELECT
            gen_random_uuid(),
            '{default_company_id}',
            user_id,
            role::text,
            'company',
            '{default_company_id}'::uuid,
            locale_scopes,
            now()
        FROM users
        WHERE role != 'admin' AND is_active = true
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    """Drop role_assignments table."""
    op.drop_table("role_assignments")


