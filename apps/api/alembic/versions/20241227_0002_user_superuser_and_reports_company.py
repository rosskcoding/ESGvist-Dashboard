"""Add is_superuser to users, company_id and structure_status to reports.

Revision ID: 20241227_0002
Revises: 20241227_0001
Create Date: 2024-12-27

Platform admin flag + tenant binding for reports + structure freeze support.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20241227_0002"
down_revision: str = "20241227_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add is_superuser to users, company_id and structure_status to reports."""

    # 1. Add is_superuser flag to users
    op.add_column(
        "users",
        sa.Column(
            "is_superuser",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # 2. Migrate existing admins to superuser
    op.execute("""
        UPDATE users
        SET is_superuser = true
        WHERE role = 'admin'
    """)

    # 3. Create default company for existing data
    # Using a fixed UUID so we can reference it in the same migration
    default_company_id = "00000000-0000-0000-0000-000000000001"
    op.execute(f"""
        INSERT INTO companies (company_id, name, status, created_at_utc, updated_at_utc)
        VALUES ('{default_company_id}', 'Default Company', 'active', now(), now())
        ON CONFLICT DO NOTHING
    """)

    # 4. Add company_id to reports (nullable first for backfill)
    op.add_column(
        "reports",
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )

    # 5. Backfill all existing reports with default company
    op.execute(f"""
        UPDATE reports
        SET company_id = '{default_company_id}'
        WHERE company_id IS NULL
    """)

    # 6. Make company_id NOT NULL and add FK
    op.alter_column("reports", "company_id", nullable=False)
    op.create_foreign_key(
        "fk_reports_company",
        "reports",
        "companies",
        ["company_id"],
        ["company_id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_reports_company", "reports", ["company_id"])

    # 7. Add structure_status to reports
    op.add_column(
        "reports",
        sa.Column(
            "structure_status",
            sa.String(20),
            nullable=False,
            server_default="draft",
        ),
    )
    op.create_check_constraint(
        "ck_reports_structure_status",
        "reports",
        "structure_status IN ('draft', 'frozen')",
    )

    # 8. Create memberships for all existing users in default company
    # Admins become owners, others become regular members
    op.execute(f"""
        INSERT INTO company_memberships (
            membership_id, company_id, user_id, is_owner, is_admin, is_active,
            created_at_utc, updated_at_utc
        )
        SELECT
            gen_random_uuid(),
            '{default_company_id}',
            user_id,
            CASE WHEN role = 'admin' THEN true ELSE false END,
            CASE WHEN role = 'admin' THEN true ELSE false END,
            is_active,
            now(),
            now()
        FROM users
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    """Remove is_superuser from users, company_id and structure_status from reports."""

    # Remove structure_status
    op.drop_constraint("ck_reports_structure_status", "reports", type_="check")
    op.drop_column("reports", "structure_status")

    # Remove company_id from reports
    op.drop_index("ix_reports_company", "reports")
    op.drop_constraint("fk_reports_company", "reports", type_="foreignkey")
    op.drop_column("reports", "company_id")

    # Remove memberships for default company (they'll be recreated if needed)
    op.execute("""
        DELETE FROM company_memberships
        WHERE company_id = '00000000-0000-0000-0000-000000000001'
    """)

    # Remove default company
    op.execute("""
        DELETE FROM companies
        WHERE company_id = '00000000-0000-0000-0000-000000000001'
    """)

    # Remove is_superuser from users
    op.drop_column("users", "is_superuser")


