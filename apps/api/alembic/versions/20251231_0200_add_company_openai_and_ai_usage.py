"""Add company OpenAI keys and AI usage tracking.

Revision ID: add_company_openai_ai_usage
Revises: add_artifact_error_code
Create Date: 2025-12-31
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "add_company_openai_ai_usage"
down_revision = "add_artifact_error_code"
branch_labels = None
depends_on = None


# Enum values
OPENAI_KEY_STATUS_VALUES = ["active", "invalid", "disabled"]
AI_FEATURE_VALUES = ["incident_help", "translation"]


def upgrade() -> None:
    """Add OpenAI key fields to companies and create ai_usage_events table."""

    # Create openai_key_status enum once, then reuse in columns without auto-create.
    openai_key_status_enum = postgresql.ENUM(
        *OPENAI_KEY_STATUS_VALUES,
        name="openai_key_status",
        create_type=False,
    )
    openai_key_status_enum.create(op.get_bind(), checkfirst=True)

    # Create ai_feature enum once, then reuse in columns without auto-create.
    ai_feature_enum = postgresql.ENUM(
        *AI_FEATURE_VALUES,
        name="ai_feature",
        create_type=False,
    )
    ai_feature_enum.create(op.get_bind(), checkfirst=True)

    # Add OpenAI key columns to companies table
    op.add_column(
        "companies",
        sa.Column(
            "openai_api_key_encrypted",
            sa.Text,
            nullable=True,
        ),
    )
    op.add_column(
        "companies",
        sa.Column(
            "openai_key_status",
            openai_key_status_enum,
            nullable=False,
            server_default="disabled",
        ),
    )
    op.add_column(
        "companies",
        sa.Column(
            "openai_key_last_validated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # Create ai_usage_events table
    op.create_table(
        "ai_usage_events",
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.company_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "timestamp_utc",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "feature",
            ai_feature_enum,
            nullable=False,
        ),
        sa.Column(
            "model",
            sa.String(100),
            nullable=False,
        ),
        sa.Column(
            "input_tokens",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "output_tokens",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "estimated_cost_usd",
            sa.Numeric(10, 6),
            nullable=False,
            server_default="0.0",
        ),
        sa.Column(
            "metadata_json",
            postgresql.JSONB,
            nullable=True,
        ),
    )

    # Create indexes
    op.create_index("ix_ai_usage_events_company_id", "ai_usage_events", ["company_id"])
    op.create_index("ix_ai_usage_events_timestamp_utc", "ai_usage_events", ["timestamp_utc"])
    op.create_index("ix_ai_usage_events_feature", "ai_usage_events", ["feature"])


def downgrade() -> None:
    """Remove OpenAI key fields and ai_usage_events table."""

    # Drop ai_usage_events table
    op.drop_index("ix_ai_usage_events_feature", "ai_usage_events")
    op.drop_index("ix_ai_usage_events_timestamp_utc", "ai_usage_events")
    op.drop_index("ix_ai_usage_events_company_id", "ai_usage_events")
    op.drop_table("ai_usage_events")

    # Remove OpenAI key columns from companies
    op.drop_column("companies", "openai_key_last_validated_at")
    op.drop_column("companies", "openai_key_status")
    op.drop_column("companies", "openai_api_key_encrypted")

    # Drop enum types
    ai_feature_enum = postgresql.ENUM(
        *AI_FEATURE_VALUES,
        name="ai_feature",
        create_type=False,
    )
    ai_feature_enum.drop(op.get_bind(), checkfirst=True)

    openai_key_status_enum = postgresql.ENUM(
        *OPENAI_KEY_STATUS_VALUES,
        name="openai_key_status",
        create_type=False,
    )
    openai_key_status_enum.drop(op.get_bind(), checkfirst=True)

