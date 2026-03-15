"""Add video block support

Revision ID: 20251231_0300
Revises: 20251231_0200
Create Date: 2025-12-31 03:00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '20251231_0300'
down_revision = 'add_company_openai_ai_usage'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add VIDEO block type and video/captions asset kinds.

    Also adds expression indexes for efficient video block queries.
    """
    # NOTE:
    # - ALTER TYPE ... ADD VALUE and CREATE INDEX CONCURRENTLY cannot run inside a transaction.
    # - Alembic env uses begin_transaction(), so we must use autocommit_block().
    with op.get_context().autocommit_block():
        # Add VIDEO to block_type enum
        op.execute("ALTER TYPE block_type ADD VALUE IF NOT EXISTS 'video'")

        # Add VIDEO and CAPTIONS to asset_kind enum
        op.execute("ALTER TYPE asset_kind ADD VALUE IF NOT EXISTS 'video'")
        op.execute("ALTER TYPE asset_kind ADD VALUE IF NOT EXISTS 'captions'")

        # Expression indexes for video blocks (JSONB queries)
        # These enable fast queries for admin dashboards and background jobs

        # Index for finding video blocks by status
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_blocks_video_status
            ON blocks ((data_json->>'status'))
            WHERE type = 'video'
            """
        )

        # Index for finding video blocks by poster generation status
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_blocks_video_poster_status
            ON blocks ((data_json->>'poster_status'))
            WHERE type = 'video'
            """
        )

        # Composite index for processing jobs (find all pending/failed posters in a report)
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_blocks_video_processing
            ON blocks (report_id, (data_json->>'poster_status'))
            WHERE type = 'video'
              AND (data_json->>'poster_status') IN ('pending', 'failed')
            """
        )


def downgrade() -> None:
    """
    Remove video block indexes.

    Note: Cannot remove enum values in PostgreSQL once added.
    Enum values (video, captions) will remain but won't be used.
    """
    # DROP INDEX CONCURRENTLY also cannot run inside a transaction.
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_blocks_video_processing")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_blocks_video_poster_status")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_blocks_video_status")

    # Cannot remove enum values in PostgreSQL
    # If you need to remove them, you must:
    # 1. Create new enum type without the values
    # 2. Alter all columns to use new enum
    # 3. Drop old enum
    # This is complex and risky, so we leave values in place.

