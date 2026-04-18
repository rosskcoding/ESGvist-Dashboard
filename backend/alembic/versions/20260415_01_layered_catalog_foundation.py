"""restore layered catalog foundation migration

Revision ID: 20260415_01
Revises: 20260325_08
Create Date: 2026-04-15 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260415_01"
down_revision: str | None = "20260325_08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_column(table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in _inspector().get_columns(table_name))


def _has_index(table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in _inspector().get_indexes(table_name))


def upgrade() -> None:
    if not _has_column("shared_elements", "element_key"):
        op.add_column("shared_elements", sa.Column("element_key", sa.String(), nullable=True))
    if not _has_column("shared_elements", "owner_layer"):
        op.add_column(
            "shared_elements",
            sa.Column("owner_layer", sa.String(), nullable=False, server_default="internal_catalog"),
        )
    if not _has_column("shared_elements", "organization_id"):
        op.add_column("shared_elements", sa.Column("organization_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_shared_elements_organization_id_organizations",
            "shared_elements",
            "organizations",
            ["organization_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if not _has_column("shared_elements", "source_element_key"):
        op.add_column("shared_elements", sa.Column("source_element_key", sa.String(), nullable=True))
    if not _has_column("shared_elements", "lifecycle_status"):
        op.add_column(
            "shared_elements",
            sa.Column("lifecycle_status", sa.String(), nullable=False, server_default="active"),
        )
    if not _has_column("shared_elements", "is_custom"):
        op.add_column(
            "shared_elements",
            sa.Column("is_custom", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    op.execute(
        """
        UPDATE shared_elements
        SET
          owner_layer = COALESCE(owner_layer, 'internal_catalog'),
          lifecycle_status = COALESCE(lifecycle_status, 'active'),
          is_custom = COALESCE(is_custom, false),
          element_key = COALESCE(
            NULLIF(element_key, ''),
            CASE
              WHEN COALESCE(owner_layer, 'internal_catalog') = 'tenant_catalog' AND organization_id IS NOT NULL
                THEN 'tenant:' || organization_id::text || ':' || regexp_replace(lower(code), '[^a-z0-9]+', '-', 'g')
              ELSE 'internal:' || regexp_replace(lower(code), '[^a-z0-9]+', '-', 'g')
            END
          )
        """
    )
    op.alter_column("shared_elements", "element_key", nullable=False)

    if not _has_index("shared_elements", "uq_shared_elements_element_key"):
        op.create_index(
            "uq_shared_elements_element_key",
            "shared_elements",
            ["element_key"],
            unique=True,
        )

    if not _has_column("disclosure_requirements", "disclosure_key"):
        op.add_column("disclosure_requirements", sa.Column("disclosure_key", sa.String(), nullable=True))
    op.execute(
        """
        UPDATE disclosure_requirements dr
        SET disclosure_key = COALESCE(
          NULLIF(disclosure_key, ''),
          regexp_replace(lower(s.code || '-' || dr.code), '[^a-z0-9]+', '-', 'g')
        )
        FROM standards s
        WHERE s.id = dr.standard_id
        """
    )

    if not _has_column("requirement_items", "catalog_key"):
        op.add_column("requirement_items", sa.Column("catalog_key", sa.String(), nullable=True))
    op.execute(
        """
        UPDATE requirement_items ri
        SET catalog_key = COALESCE(
          NULLIF(catalog_key, ''),
          regexp_replace(
            lower(
              COALESCE(dr.disclosure_key, s.code || '-' || dr.code) || '-' ||
              COALESCE(NULLIF(ri.item_code, ''), ri.id::text)
            ),
            '[^a-z0-9]+',
            '-',
            'g'
          )
        )
        FROM disclosure_requirements dr
        JOIN standards s ON s.id = dr.standard_id
        WHERE dr.id = ri.disclosure_requirement_id
        """
    )


def downgrade() -> None:
    # Compatibility migration kept intentionally reversible only for objects it created.
    if _has_index("shared_elements", "uq_shared_elements_element_key"):
        op.drop_index("uq_shared_elements_element_key", table_name="shared_elements")
    if _has_column("requirement_items", "catalog_key"):
        op.drop_column("requirement_items", "catalog_key")
    if _has_column("disclosure_requirements", "disclosure_key"):
        op.drop_column("disclosure_requirements", "disclosure_key")
    if _has_column("shared_elements", "is_custom"):
        op.drop_column("shared_elements", "is_custom")
    if _has_column("shared_elements", "lifecycle_status"):
        op.drop_column("shared_elements", "lifecycle_status")
    if _has_column("shared_elements", "source_element_key"):
        op.drop_column("shared_elements", "source_element_key")
    if _has_column("shared_elements", "organization_id"):
        op.drop_constraint(
            "fk_shared_elements_organization_id_organizations",
            "shared_elements",
            type_="foreignkey",
        )
        op.drop_column("shared_elements", "organization_id")
    if _has_column("shared_elements", "owner_layer"):
        op.drop_column("shared_elements", "owner_layer")
    if _has_column("shared_elements", "element_key"):
        op.drop_column("shared_elements", "element_key")
