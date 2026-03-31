#!/usr/bin/env python3

import argparse
import asyncio
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.models.completeness import DisclosureRequirementStatus, RequirementItemDataPoint, RequirementItemStatus
from app.db.models.data_point import DataPoint
from app.db.models.project import MetricAssignment, ReportingProject, ReportingProjectStandard
from app.db.models.standard import Standard
from app.services.standard_catalog import resolve_standard_catalog_meta


DEFAULT_STANDARD_CODES = [
    "GRI 2",
    "GRI 3",
    "GRI 305",
    "GRI 405",
    "GRI 14",
    "SASB-SV-AD",
    "SASB-FN-AC",
    "IFRS-S2",
    "ESRS",
]


@dataclass
class ResetStats:
    deleted_project_standards: int = 0
    deleted_metric_assignments: int = 0
    deleted_requirement_item_statuses: int = 0
    deleted_disclosure_statuses: int = 0
    deleted_requirement_item_data_points: int = 0
    deleted_data_points: int = 0
    created_project_standards: int = 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reset a demo project's attached standards and collection data."
    )
    parser.add_argument("project_id", type=int, help="Reporting project id to reset")
    parser.add_argument(
        "--attach",
        action="append",
        dest="attach_codes",
        help="Standard code to attach after reset. Repeatable. Defaults to a demo mix of GRI/SASB/IFRS/ESRS.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist the reset. Without this flag the script runs as dry-run.",
    )
    return parser


async def reset_project_catalog(
    *,
    project_id: int,
    standard_codes: list[str],
    apply_changes: bool,
) -> ResetStats:
    stats = ResetStats()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        project = await session.scalar(
            select(ReportingProject).where(ReportingProject.id == project_id)
        )
        if project is None:
            raise RuntimeError(f"Project {project_id} not found")

        requested_codes = list(dict.fromkeys(code.strip() for code in standard_codes if code.strip()))
        standards = (
            await session.execute(
                select(Standard).where(Standard.code.in_(requested_codes))
            )
        ).scalars().all()
        standards_by_code = {standard.code: standard for standard in standards}
        missing_codes = [code for code in requested_codes if code not in standards_by_code]
        if missing_codes:
            raise RuntimeError(f"Requested standards not found: {', '.join(missing_codes)}")

        for code in requested_codes:
            standard = standards_by_code[code]
            meta = resolve_standard_catalog_meta(standard.code, standard.name)
            if not meta.is_attachable:
                raise RuntimeError(f"Standard {standard.code} is not attachable")

        delete_specs = [
            ("requirement_item_data_points", RequirementItemDataPoint, RequirementItemDataPoint.reporting_project_id == project_id),
            ("disclosure_requirement_statuses", DisclosureRequirementStatus, DisclosureRequirementStatus.reporting_project_id == project_id),
            ("requirement_item_statuses", RequirementItemStatus, RequirementItemStatus.reporting_project_id == project_id),
            ("metric_assignments", MetricAssignment, MetricAssignment.reporting_project_id == project_id),
            ("data_points", DataPoint, DataPoint.reporting_project_id == project_id),
            ("reporting_project_standards", ReportingProjectStandard, ReportingProjectStandard.reporting_project_id == project_id),
        ]

        for label, model, condition in delete_specs:
            result = await session.execute(delete(model).where(condition))
            affected = result.rowcount or 0
            if label == "reporting_project_standards":
                stats.deleted_project_standards = affected
            elif label == "metric_assignments":
                stats.deleted_metric_assignments = affected
            elif label == "requirement_item_statuses":
                stats.deleted_requirement_item_statuses = affected
            elif label == "disclosure_requirement_statuses":
                stats.deleted_disclosure_statuses = affected
            elif label == "requirement_item_data_points":
                stats.deleted_requirement_item_data_points = affected
            elif label == "data_points":
                stats.deleted_data_points = affected

        for code in requested_codes:
            standard = standards_by_code[code]
            session.add(
                ReportingProjectStandard(
                    reporting_project_id=project_id,
                    standard_id=standard.id,
                    is_base_standard=False,
                )
            )
            stats.created_project_standards += 1

        if apply_changes:
            await session.commit()
        else:
            await session.rollback()

    await engine.dispose()
    return stats


async def main() -> None:
    args = build_parser().parse_args()
    standard_codes = args.attach_codes or DEFAULT_STANDARD_CODES
    stats = await reset_project_catalog(
        project_id=args.project_id,
        standard_codes=standard_codes,
        apply_changes=args.apply,
    )
    mode = "apply" if args.apply else "dry-run"
    print(f"Mode: {mode}")
    print(f"Project: {args.project_id}")
    print(f"Attach: {', '.join(standard_codes)}")
    print(f"  Deleted project standards:        {stats.deleted_project_standards}")
    print(f"  Deleted metric assignments:       {stats.deleted_metric_assignments}")
    print(f"  Deleted item statuses:            {stats.deleted_requirement_item_statuses}")
    print(f"  Deleted disclosure statuses:      {stats.deleted_disclosure_statuses}")
    print(f"  Deleted item-data bindings:       {stats.deleted_requirement_item_data_points}")
    print(f"  Deleted data points:              {stats.deleted_data_points}")
    print(f"  Created project standards:        {stats.created_project_standards}")


if __name__ == "__main__":
    asyncio.run(main())
