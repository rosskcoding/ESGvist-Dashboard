"""Reconcile schema drift for dataset timestamps and enum-backed columns.

Revision ID: 20260213_2200
Revises: 20260105_0100
Create Date: 2026-02-13 22:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260213_2200"
down_revision: str = "20260105_0100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ENUM_COLUMN_SPECS: list[tuple[str, str, str, tuple[str, ...], str | None, int]] = [
    ("companies", "status", "company_status_enum", ("active", "disabled"), "active", 20),
    ("reports", "structure_status", "structure_status_enum", ("draft", "frozen"), "draft", 20),
    ("release_builds", "audit_basis", "audit_basis_enum", ("snapshot", "live"), "snapshot", 20),
    (
        "audit_pack_jobs",
        "status",
        "job_status",
        ("queued", "running", "partial_success", "failed", "success", "cancelled"),
        "queued",
        20,
    ),
    (
        "comment_threads",
        "anchor_type",
        "comment_thread_anchor_type_enum",
        ("report", "section", "block"),
        None,
        20,
    ),
    ("comment_threads", "status", "thread_status_enum", ("open", "resolved"), "open", 20),
    (
        "evidence_items",
        "scope_type",
        "evidence_scope_type_enum",
        ("report", "section", "block"),
        None,
        20,
    ),
    ("evidence_items", "type", "evidence_type_enum", ("file", "link", "note"), None, 10),
    ("evidence_items", "source", "evidence_source_enum", ("internal", "external"), None, 20),
    (
        "evidence_items",
        "visibility",
        "evidence_visibility_enum",
        ("team", "audit", "restricted"),
        "team",
        20,
    ),
    (
        "audit_checks",
        "target_type",
        "audit_check_target_type_enum",
        ("report", "section", "block", "evidence_item"),
        None,
        20,
    ),
    (
        "audit_checks",
        "status",
        "audit_check_status_enum",
        ("not_started", "in_review", "reviewed", "flagged", "needs_info"),
        "not_started",
        20,
    ),
    (
        "audit_checks",
        "severity",
        "audit_check_severity_enum",
        ("critical", "major", "minor", "info"),
        None,
        20,
    ),
]


def _quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    exists_query = sa.text(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = :table_name
          AND column_name = :column_name
        LIMIT 1
        """
    )
    return bind.execute(exists_query, {"table_name": table_name, "column_name": column_name}).scalar() is not None


def _column_udt_name(table_name: str, column_name: str) -> str | None:
    bind = op.get_bind()
    udt_query = sa.text(
        """
        SELECT udt_name
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = :table_name
          AND column_name = :column_name
        """
    )
    return bind.execute(udt_query, {"table_name": table_name, "column_name": column_name}).scalar_one_or_none()


def _ensure_enum_type(enum_name: str, labels: tuple[str, ...]) -> None:
    labels_sql = ", ".join(_quote_literal(label) for label in labels)
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_type t
                    JOIN pg_namespace n ON n.oid = t.typnamespace
                    WHERE n.nspname = current_schema()
                      AND t.typname = '{enum_name}'
                ) THEN
                    CREATE TYPE {enum_name} AS ENUM ({labels_sql});
                END IF;
            END $$;
            """
        )
    )

    # Ensure required labels exist in existing enum type.
    for label in labels:
        op.execute(sa.text(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS {_quote_literal(label)}"))


def _collect_invalid_values(table_name: str, column_name: str, labels: tuple[str, ...]) -> list[str]:
    bind = op.get_bind()
    allowed_values_sql = ", ".join(_quote_literal(label) for label in labels)
    invalid_query = sa.text(
        f"""
        SELECT DISTINCT {column_name}::text
        FROM {table_name}
        WHERE {column_name} IS NOT NULL
          AND {column_name}::text NOT IN ({allowed_values_sql})
        ORDER BY {column_name}::text
        """
    )
    return [row[0] for row in bind.execute(invalid_query).all()]


def _convert_column_to_enum(
    table_name: str,
    column_name: str,
    enum_name: str,
    labels: tuple[str, ...],
    default: str | None,
) -> None:
    if not _column_exists(table_name, column_name):
        return

    _ensure_enum_type(enum_name, labels)
    current_udt = _column_udt_name(table_name, column_name)

    if current_udt == enum_name:
        if default is not None:
            op.execute(
                sa.text(
                    f"ALTER TABLE {table_name} ALTER COLUMN {column_name} "
                    f"SET DEFAULT {_quote_literal(default)}::{enum_name}"
                )
            )
        return

    invalid_values = _collect_invalid_values(table_name, column_name, labels)
    if invalid_values:
        raise RuntimeError(
            f"Cannot convert {table_name}.{column_name} to enum {enum_name}: "
            f"invalid values present: {invalid_values}"
        )

    op.execute(sa.text(f"ALTER TABLE {table_name} ALTER COLUMN {column_name} DROP DEFAULT"))
    op.execute(
        sa.text(
            f"ALTER TABLE {table_name} ALTER COLUMN {column_name} "
            f"TYPE {enum_name} USING {column_name}::text::{enum_name}"
        )
    )

    if default is not None:
        op.execute(
            sa.text(
                f"ALTER TABLE {table_name} ALTER COLUMN {column_name} "
                f"SET DEFAULT {_quote_literal(default)}::{enum_name}"
            )
        )


def _convert_column_to_varchar(
    table_name: str,
    column_name: str,
    enum_name: str,
    default: str | None,
    length: int,
) -> None:
    if not _column_exists(table_name, column_name):
        return

    current_udt = _column_udt_name(table_name, column_name)
    if current_udt != enum_name:
        return

    op.execute(sa.text(f"ALTER TABLE {table_name} ALTER COLUMN {column_name} DROP DEFAULT"))
    op.execute(
        sa.text(
            f"ALTER TABLE {table_name} ALTER COLUMN {column_name} "
            f"TYPE VARCHAR({length}) USING {column_name}::text"
        )
    )

    if default is not None:
        op.execute(
            sa.text(
                f"ALTER TABLE {table_name} ALTER COLUMN {column_name} "
                f"SET DEFAULT {_quote_literal(default)}::character varying"
            )
        )


def _rename_column_if_needed(table_name: str, old_name: str, new_name: str) -> None:
    if _column_exists(table_name, old_name) and not _column_exists(table_name, new_name):
        op.alter_column(table_name, old_name, new_column_name=new_name)


def upgrade() -> None:
    """Apply schema reconciliation fixes."""
    _rename_column_if_needed("datasets", "created_at", "created_at_utc")
    _rename_column_if_needed("datasets", "updated_at", "updated_at_utc")

    for table_name, column_name, enum_name, labels, default, _length in ENUM_COLUMN_SPECS:
        _convert_column_to_enum(table_name, column_name, enum_name, labels, default)


def downgrade() -> None:
    """Revert schema reconciliation fixes."""
    for table_name, column_name, enum_name, _labels, default, length in reversed(ENUM_COLUMN_SPECS):
        _convert_column_to_varchar(table_name, column_name, enum_name, default, length)

    _rename_column_if_needed("datasets", "updated_at_utc", "updated_at")
    _rename_column_if_needed("datasets", "created_at_utc", "created_at")
