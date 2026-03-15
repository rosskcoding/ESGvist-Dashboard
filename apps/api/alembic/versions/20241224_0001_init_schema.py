"""Initial schema setup.

Revision ID: 0001
Revises:
Create Date: 2024-12-24

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create initial schema: users, reports, sections, blocks, assets."""

    # Ensure UUID generation function exists (gen_random_uuid()).
    # Required because we use server_default=gen_random_uuid() in primary keys.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # Enum types are created automatically by sa.Enum() in op.create_table()

    # Users table
    op.create_table(
        "users",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "admin", "editor", "reviewer", "translator", "exporter", "viewer", name="user_role"
            ),
            nullable=False,
            server_default="viewer",
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("locale_scopes", postgresql.ARRAY(sa.String), nullable=True),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at_utc",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Reports table
    op.create_table(
        "reports",
        sa.Column(
            "report_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("year", sa.SmallInteger, nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column(
            "source_locale",
            sa.Enum("ru", "en", "kk", name="locale"),
            nullable=False,
            server_default="ru",
        ),
        sa.Column(
            "default_locale",
            sa.Enum("ru", "en", "kk", name="locale"),
            nullable=False,
            server_default="ru",
        ),
        sa.Column(
            "enabled_locales", postgresql.ARRAY(sa.String), nullable=False, server_default="{ru}"
        ),
        sa.Column(
            "release_locales", postgresql.ARRAY(sa.String), nullable=False, server_default="{ru}"
        ),
        sa.Column("theme_slug", sa.String(50), nullable=False, server_default="default"),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at_utc",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("year >= 2000 AND year <= 2100", name="ck_reports_year_range"),
    )
    op.create_index("ix_reports_year", "reports", ["year"])

    # Sections table
    op.create_table(
        "sections",
        sa.Column(
            "section_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reports.report_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_section_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sections.section_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("order_index", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at_utc",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_sections_report_order",
        "sections",
        ["report_id", "parent_section_id", "order_index"],
        unique=True,
    )

    # Section i18n table
    op.create_table(
        "section_i18n",
        sa.Column(
            "section_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sections.section_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("locale", sa.Enum("ru", "en", "kk", name="locale"), primary_key=True),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
    )
    op.create_index("ix_section_i18n_slug", "section_i18n", ["section_id", "locale"])

    # Blocks table
    op.create_table(
        "blocks",
        sa.Column(
            "block_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reports.report_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "section_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sections.section_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "type",
            sa.Enum(
                "text",
                "kpi_cards",
                "table",
                "chart",
                "image",
                "quote",
                "downloads",
                "accordion",
                "timeline",
                "custom",
                name="block_type",
            ),
            nullable=False,
        ),
        sa.Column(
            "variant",
            sa.Enum("default", "compact", "emphasized", "full_width", name="block_variant"),
            nullable=False,
            server_default="default",
        ),
        sa.Column("order_index", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("data_json", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "qa_flags_global", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"
        ),
        sa.Column(
            "custom_override_enabled", sa.Boolean, nullable=False, server_default=sa.text("false")
        ),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "owner_user_id",
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
        sa.Column(
            "updated_at_utc",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_blocks_section_order", "blocks", ["section_id", "order_index"])
    op.create_index("ix_blocks_report", "blocks", ["report_id"])

    # Block i18n table
    op.create_table(
        "block_i18n",
        sa.Column(
            "block_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("blocks.block_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("locale", sa.Enum("ru", "en", "kk", name="locale"), primary_key=True),
        sa.Column(
            "status",
            sa.Enum("draft", "ready", "qa_required", "approved", name="content_status"),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "qa_flags_by_locale", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"
        ),
        sa.Column("fields_json", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("custom_html_sanitized", sa.Text, nullable=True),
        sa.Column("custom_css_validated", sa.Text, nullable=True),
        sa.Column("last_approved_at_utc", sa.DateTime(timezone=True), nullable=True),
    )

    # Assets table
    op.create_table(
        "assets",
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "kind", sa.Enum("image", "font", "attachment", name="asset_kind"), nullable=False
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_assets_sha256", "assets", ["sha256"])

    # Asset links (many-to-many blocks <-> assets)
    op.create_table(
        "asset_links",
        sa.Column(
            "block_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("blocks.block_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assets.asset_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("purpose", sa.String(50), nullable=False, server_default="content"),
    )

    # Source snapshots table
    op.create_table(
        "source_snapshots",
        sa.Column(
            "snapshot_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reports.report_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content_root_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Release builds table
    op.create_table(
        "release_builds",
        sa.Column(
            "build_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reports.report_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("build_type", sa.Enum("draft", "release", name="build_type"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("queued", "running", "failed", "success", name="build_status"),
            nullable=False,
            server_default="queued",
        ),
        sa.Column(
            "source_snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("source_snapshots.snapshot_id"),
            nullable=True,
        ),
        sa.Column("theme_slug", sa.String(50), nullable=False),
        sa.Column("base_path", sa.String(200), nullable=False, server_default="/"),
        sa.Column("locales", postgresql.ARRAY(sa.String), nullable=False),
        sa.Column("zip_path", sa.String(500), nullable=True),
        sa.Column("zip_sha256", sa.String(64), nullable=True),
        sa.Column("manifest_path", sa.String(500), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("finished_at_utc", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_release_builds_report", "release_builds", ["report_id"])

    # Glossary terms table
    op.create_table(
        "glossary_terms",
        sa.Column(
            "term_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("ru", sa.String(500), nullable=False),
        sa.Column("en", sa.String(500), nullable=False),
        sa.Column("kk", sa.String(500), nullable=False),
        sa.Column(
            "strictness",
            sa.Enum("do_not_translate", "strict", "preferred", name="glossary_strictness"),
            nullable=False,
            server_default="preferred",
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "updated_at_utc",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Translation jobs table
    op.create_table(
        "translation_jobs",
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reports.report_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope_type", sa.String(20), nullable=False),
        sa.Column("scope_ids", postgresql.JSONB, nullable=False),
        sa.Column("source_locale", sa.Enum("ru", "en", "kk", name="locale"), nullable=False),
        sa.Column("target_locales", postgresql.ARRAY(sa.String), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False, server_default="reporting"),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "running",
                "partial_success",
                "failed",
                "success",
                "cancelled",
                name="job_status",
            ),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("progress", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("error_log", postgresql.JSONB, nullable=True),
        sa.Column("started_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_translation_jobs_report", "translation_jobs", ["report_id"])

    # Translation units table
    op.create_table(
        "translation_units",
        sa.Column(
            "tu_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("chunk_id", sa.String(200), nullable=False),
        sa.Column(
            "block_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("blocks.block_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("field_name", sa.String(50), nullable=False),
        sa.Column("chunk_index", sa.SmallInteger, nullable=False),
        sa.Column("source_locale", sa.Enum("ru", "en", "kk", name="locale"), nullable=False),
        sa.Column("target_locale", sa.Enum("ru", "en", "kk", name="locale"), nullable=False),
        sa.Column("source_text", sa.Text, nullable=False),
        sa.Column("target_text", sa.Text, nullable=True),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "translated",
                "imported",
                "qa_required",
                "approved",
                "failed",
                name="translation_status",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("qa_flags", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("placeholders_json", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at_utc",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_translation_units_chunk", "translation_units", ["chunk_id"])
    op.create_index("ix_translation_units_hash", "translation_units", ["source_hash"])
    op.create_index("ix_translation_units_block", "translation_units", ["block_id"])

    # Audit events table
    op.create_table(
        "audit_events",
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "timestamp_utc",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("actor_type", sa.String(20), nullable=False),
        sa.Column("actor_id", sa.String(100), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(100), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB, nullable=True),
        sa.Column("ip_address", sa.String(50), nullable=True),
    )
    op.create_index("ix_audit_events_timestamp", "audit_events", ["timestamp_utc"])
    op.create_index("ix_audit_events_entity", "audit_events", ["entity_type", "entity_id"])
    op.create_index("ix_audit_events_actor", "audit_events", ["actor_type", "actor_id"])


def downgrade() -> None:
    """Drop all tables and types."""
    op.drop_table("audit_events")
    op.drop_table("translation_units")
    op.drop_table("translation_jobs")
    op.drop_table("glossary_terms")
    op.drop_table("release_builds")
    op.drop_table("source_snapshots")
    op.drop_table("asset_links")
    op.drop_table("assets")
    op.drop_table("block_i18n")
    op.drop_table("blocks")
    op.drop_table("section_i18n")
    op.drop_table("sections")
    op.drop_table("reports")
    op.drop_table("users")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS glossary_strictness")
    op.execute("DROP TYPE IF EXISTS job_status")
    op.execute("DROP TYPE IF EXISTS translation_status")
    op.execute("DROP TYPE IF EXISTS build_status")
    op.execute("DROP TYPE IF EXISTS build_type")
    op.execute("DROP TYPE IF EXISTS asset_kind")
    op.execute("DROP TYPE IF EXISTS block_variant")
    op.execute("DROP TYPE IF EXISTS block_type")
    op.execute("DROP TYPE IF EXISTS user_role")
    op.execute("DROP TYPE IF EXISTS content_status")
    op.execute("DROP TYPE IF EXISTS locale")
