"""Add package_mode, scope, target_section_id, target_block_id to release_builds.

Revision ID: 20241226_0002
Revises: 20241226_0001
Create Date: 2024-12-26

"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20241226_0002"
down_revision: str | None = "20241226_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add package_mode, scope, and target fields to release_builds."""
    # Create enum types
    op.execute("CREATE TYPE package_mode AS ENUM ('portable', 'interactive')")
    op.execute("CREATE TYPE build_scope AS ENUM ('full', 'section', 'block')")

    # Add columns
    op.add_column(
        "release_builds",
        sa.Column(
            "package_mode",
            sa.Enum("portable", "interactive", name="package_mode", create_type=False),
            server_default="portable",
            nullable=False,
        ),
    )
    op.add_column(
        "release_builds",
        sa.Column(
            "scope",
            sa.Enum("full", "section", "block", name="build_scope", create_type=False),
            server_default="full",
            nullable=False,
        ),
    )
    op.add_column(
        "release_builds",
        sa.Column(
            "target_section_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.add_column(
        "release_builds",
        sa.Column(
            "target_block_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )

    # Add foreign keys
    op.create_foreign_key(
        "fk_release_builds_target_section",
        "release_builds",
        "sections",
        ["target_section_id"],
        ["section_id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_release_builds_target_block",
        "release_builds",
        "blocks",
        ["target_block_id"],
        ["block_id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Remove package_mode, scope, and target fields from release_builds."""
    # Drop foreign keys
    op.drop_constraint("fk_release_builds_target_block", "release_builds", type_="foreignkey")
    op.drop_constraint("fk_release_builds_target_section", "release_builds", type_="foreignkey")

    # Drop columns
    op.drop_column("release_builds", "target_block_id")
    op.drop_column("release_builds", "target_section_id")
    op.drop_column("release_builds", "scope")
    op.drop_column("release_builds", "package_mode")

    # Drop enum types
    op.execute("DROP TYPE build_scope")
    op.execute("DROP TYPE package_mode")




