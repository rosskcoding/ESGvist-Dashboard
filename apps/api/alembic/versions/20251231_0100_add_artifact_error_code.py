"""Add artifact_error_code enum and error_code column.

Revision ID: add_artifact_error_code
Revises: add_refresh_tokens_001
Create Date: 2025-12-31
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "add_artifact_error_code"
down_revision = "add_refresh_tokens_001"
branch_labels = None
depends_on = None


# Error code enum values
ERROR_CODE_VALUES = [
    "none",
    "timeout_overall",
    "timeout_playwright",
    "timeout_download",
    "renderer_playwright_crash",
    "renderer_docx_template",
    "renderer_html_invalid",
    "build_not_found",
    "build_zip_not_found",
    "build_zip_corrupt",
    "validation_locale",
    "validation_profile",
    "unknown",
]


def upgrade() -> None:
    """Add error_code enum type and column."""
    # Create enum type
    artifact_error_code_enum = sa.Enum(
        *ERROR_CODE_VALUES,
        name="artifact_error_code",
    )
    artifact_error_code_enum.create(op.get_bind(), checkfirst=True)

    # Add column with default value
    op.add_column(
        "release_build_artifacts",
        sa.Column(
            "error_code",
            artifact_error_code_enum,
            nullable=False,
            server_default="none",
        ),
    )


def downgrade() -> None:
    """Remove error_code column and enum type."""
    # Drop column
    op.drop_column("release_build_artifacts", "error_code")

    # Drop enum type
    artifact_error_code_enum = sa.Enum(
        *ERROR_CODE_VALUES,
        name="artifact_error_code",
    )
    artifact_error_code_enum.drop(op.get_bind(), checkfirst=True)


