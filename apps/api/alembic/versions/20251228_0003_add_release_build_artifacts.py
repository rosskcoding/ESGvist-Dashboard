"""Add release_build_artifacts table and build_options column.

Revision ID: 20251228_0003
Revises: 20251228_0002
Create Date: 2024-12-28

Export v2: Support for PDF and DOCX artifact generation.
- New table: release_build_artifacts (tracks individual artifacts)
- New column: release_builds.build_options (JSONB for targets, profile, etc.)
- New enums: artifact_format, artifact_status
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20251228_0003"
down_revision: str = "20251228_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add release_build_artifacts table and build_options column."""

    # 1. Create artifact_format enum (if not exists)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE artifact_format AS ENUM ('zip', 'print_html', 'pdf', 'docx');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # 2. Create artifact_status enum (if not exists)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE artifact_status AS ENUM ('queued', 'processing', 'done', 'failed', 'cancelled');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # 3. Create release_build_artifacts table using raw SQL to avoid enum auto-creation
    op.execute("""
        CREATE TABLE release_build_artifacts (
            artifact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            build_id UUID NOT NULL REFERENCES release_builds(build_id) ON DELETE CASCADE,
            format artifact_format NOT NULL,
            locale VARCHAR(10),
            profile VARCHAR(20),
            status artifact_status NOT NULL DEFAULT 'queued',
            path VARCHAR(500),
            sha256 VARCHAR(64),
            size_bytes INTEGER,
            error_message TEXT,
            created_at_utc TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at_utc TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # 4. Create indexes
    op.create_index(
        "ix_release_build_artifacts_build_id",
        "release_build_artifacts",
        ["build_id"],
    )

    # 5. Create unique constraint for (build_id, format, locale, profile)
    op.create_unique_constraint(
        "uq_release_build_artifacts_build_format_locale_profile",
        "release_build_artifacts",
        ["build_id", "format", "locale", "profile"],
    )

    # 6. Add build_options column to release_builds
    op.add_column(
        "release_builds",
        sa.Column(
            "build_options",
            postgresql.JSONB,
            nullable=True,
            comment="Build options: targets, pdf_profile, include_toc, etc.",
        ),
    )


def downgrade() -> None:
    """Remove release_build_artifacts table and build_options column."""

    # 1. Remove build_options column
    op.drop_column("release_builds", "build_options")

    # 2. Drop release_build_artifacts table (includes constraints)
    op.execute("DROP TABLE IF EXISTS release_build_artifacts CASCADE")

    # 3. Drop enums
    op.execute("DROP TYPE IF EXISTS artifact_status")
    op.execute("DROP TYPE IF EXISTS artifact_format")

