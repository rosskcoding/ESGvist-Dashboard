"""Drop legacy user.role field.

Legacy roles (admin, editor, reviewer, translator, exporter, viewer)
are no longer used. Real roles are now assigned via RoleAssignment table.

Revision ID: 20251230_0001
Revises: 20251228_0003_add_release_build_artifacts
Create Date: 2025-12-30

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20251230_0001"
down_revision = "20251228_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove legacy role column and enum type."""
    # Drop the role column from users table
    op.drop_column("users", "role")

    # Drop the user_role enum type
    op.execute("DROP TYPE IF EXISTS user_role")


def downgrade() -> None:
    """Restore legacy role column (all users get 'viewer' as default)."""
    # Recreate the enum type
    op.execute("""
        CREATE TYPE user_role AS ENUM (
            'admin', 'editor', 'reviewer', 'translator', 'exporter', 'viewer'
        )
    """)

    # Add back the role column with default 'viewer'
    op.execute("""
        ALTER TABLE users
        ADD COLUMN role user_role NOT NULL DEFAULT 'viewer'
    """)

