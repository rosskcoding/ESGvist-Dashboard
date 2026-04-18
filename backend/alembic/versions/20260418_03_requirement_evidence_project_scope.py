"""scope requirement evidence links to reporting projects

Revision ID: 20260418_03
Revises: 20260418_02
Create Date: 2026-04-18 19:40:00.000000
"""

from collections import defaultdict
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260418_03"
down_revision: str | None = "20260418_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "requirement_item_evidences"
PROJECT_COLUMN = "reporting_project_id"
OLD_UNIQUE = "uq_ri_evidence"
NEW_UNIQUE = "uq_ri_evidence_project"
PROJECT_FK = "fk_requirement_item_evidences_reporting_project_id"
PROJECT_INDEX = f"ix_{TABLE_NAME}_{PROJECT_COLUMN}"


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return table_name in _inspector().get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in _inspector().get_columns(table_name))


def _has_unique_constraint(table_name: str, constraint_name: str) -> bool:
    return any(
        constraint["name"] == constraint_name
        for constraint in _inspector().get_unique_constraints(table_name)
    )


def _has_foreign_key(table_name: str, constraint_name: str) -> bool:
    return any(fk["name"] == constraint_name for fk in _inspector().get_foreign_keys(table_name))


def _has_index(table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in _inspector().get_indexes(table_name))


def _backfill_requirement_item_evidence_projects() -> None:
    bind = op.get_bind()

    rie = sa.table(
        TABLE_NAME,
        sa.column("id", sa.Integer()),
        sa.column("evidence_id", sa.Integer()),
        sa.column("requirement_item_id", sa.Integer()),
        sa.column(PROJECT_COLUMN, sa.Integer()),
    )
    dpe = sa.table(
        "data_point_evidences",
        sa.column("evidence_id", sa.Integer()),
        sa.column("data_point_id", sa.Integer()),
    )
    dp = sa.table(
        "data_points",
        sa.column("id", sa.Integer()),
        sa.column("reporting_project_id", sa.Integer()),
    )
    ri = sa.table(
        "requirement_items",
        sa.column("id", sa.Integer()),
        sa.column("disclosure_requirement_id", sa.Integer()),
    )
    dr = sa.table(
        "disclosure_requirements",
        sa.column("id", sa.Integer()),
        sa.column("standard_id", sa.Integer()),
    )
    std = sa.table(
        "standards",
        sa.column("id", sa.Integer()),
        sa.column("is_active", sa.Boolean()),
    )
    rps = sa.table(
        "reporting_project_standards",
        sa.column("reporting_project_id", sa.Integer()),
        sa.column("standard_id", sa.Integer()),
    )

    item_projects: dict[int, set[int]] = defaultdict(set)
    for requirement_item_id, project_id in bind.execute(
        sa.select(ri.c.id, rps.c.reporting_project_id)
        .select_from(
            ri.join(dr, dr.c.id == ri.c.disclosure_requirement_id)
            .join(std, std.c.id == dr.c.standard_id)
            .join(rps, rps.c.standard_id == std.c.id)
        )
        .where(std.c.is_active.is_(True))
    ).fetchall():
        item_projects[int(requirement_item_id)].add(int(project_id))

    evidence_projects: dict[int, set[int]] = defaultdict(set)
    for evidence_id, project_id in bind.execute(
        sa.select(dpe.c.evidence_id, dp.c.reporting_project_id)
        .select_from(dpe.join(dp, dp.c.id == dpe.c.data_point_id))
    ).fetchall():
        evidence_projects[int(evidence_id)].add(int(project_id))

    rows = bind.execute(
        sa.select(
            rie.c.id,
            rie.c.evidence_id,
            rie.c.requirement_item_id,
            rie.c.reporting_project_id,
        )
    ).fetchall()

    for row in rows:
        if row.reporting_project_id is not None:
            continue
        candidate_projects = set(item_projects.get(int(row.requirement_item_id), set()))
        linked_projects = evidence_projects.get(int(row.evidence_id), set())
        if linked_projects:
            candidate_projects &= linked_projects
        if len(candidate_projects) != 1:
            continue
        bind.execute(
            rie.update()
            .where(rie.c.id == row.id)
            .values(reporting_project_id=next(iter(candidate_projects)))
        )


def upgrade() -> None:
    if not _has_table(TABLE_NAME):
        return

    if not _has_column(TABLE_NAME, PROJECT_COLUMN):
        op.add_column(TABLE_NAME, sa.Column(PROJECT_COLUMN, sa.Integer(), nullable=True))
    if not _has_foreign_key(TABLE_NAME, PROJECT_FK):
        op.create_foreign_key(
            PROJECT_FK,
            TABLE_NAME,
            "reporting_projects",
            [PROJECT_COLUMN],
            ["id"],
            ondelete="CASCADE",
        )
    if not _has_index(TABLE_NAME, PROJECT_INDEX):
        op.create_index(PROJECT_INDEX, TABLE_NAME, [PROJECT_COLUMN], unique=False)

    _backfill_requirement_item_evidence_projects()

    if _has_unique_constraint(TABLE_NAME, OLD_UNIQUE):
        op.drop_constraint(OLD_UNIQUE, TABLE_NAME, type_="unique")
    if not _has_unique_constraint(TABLE_NAME, NEW_UNIQUE):
        op.create_unique_constraint(
            NEW_UNIQUE,
            TABLE_NAME,
            [PROJECT_COLUMN, "requirement_item_id", "evidence_id"],
        )


def downgrade() -> None:
    if not _has_table(TABLE_NAME):
        return

    if _has_unique_constraint(TABLE_NAME, NEW_UNIQUE):
        op.drop_constraint(NEW_UNIQUE, TABLE_NAME, type_="unique")
    if not _has_unique_constraint(TABLE_NAME, OLD_UNIQUE):
        op.create_unique_constraint(
            OLD_UNIQUE,
            TABLE_NAME,
            ["requirement_item_id", "evidence_id"],
        )
    if _has_index(TABLE_NAME, PROJECT_INDEX):
        op.drop_index(PROJECT_INDEX, table_name=TABLE_NAME)
    if _has_foreign_key(TABLE_NAME, PROJECT_FK):
        op.drop_constraint(PROJECT_FK, TABLE_NAME, type_="foreignkey")
    if _has_column(TABLE_NAME, PROJECT_COLUMN):
        op.drop_column(TABLE_NAME, PROJECT_COLUMN)
