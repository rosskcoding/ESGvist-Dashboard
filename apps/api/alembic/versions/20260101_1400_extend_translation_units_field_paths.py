"""Extend translation_units field path columns.

`translation_units.field_name` was originally VARCHAR(50), which is too small for
current chunk paths (e.g. chart column labels in `inline_data_i18n.column_labels.*`).
This caused worker crashes and left jobs stuck in RUNNING.

Revision ID: 20260101_1400
Revises: 20260101_1300
Create Date: 2026-01-01 14:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260101_1400"
down_revision: Union[str, None] = "20260101_1300"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make both columns unbounded to avoid truncation on long field paths.
    op.alter_column(
        "translation_units",
        "field_name",
        existing_type=sa.String(length=50),
        type_=sa.Text(),
        existing_nullable=False,
    )
    op.alter_column(
        "translation_units",
        "chunk_id",
        existing_type=sa.String(length=200),
        type_=sa.Text(),
        existing_nullable=False,
    )


def downgrade() -> None:
    # NOTE: This may fail if existing rows exceed the smaller lengths.
    op.alter_column(
        "translation_units",
        "chunk_id",
        existing_type=sa.Text(),
        type_=sa.String(length=200),
        existing_nullable=False,
    )
    op.alter_column(
        "translation_units",
        "field_name",
        existing_type=sa.Text(),
        type_=sa.String(length=50),
        existing_nullable=False,
    )


