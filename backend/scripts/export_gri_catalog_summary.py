from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.db.models.requirement_item import RequirementItem
from app.db.models.standard import DisclosureRequirement, Standard, StandardSection


@dataclass
class DataPointSummary:
    item_code: str | None
    name: str
    item_type: str
    value_type: str
    unit_code: str | None
    sort_order: int


@dataclass
class DisclosureSummary:
    code: str
    title: str
    requirement_type: str | None
    datapoint_count: int
    datapoints: list[DataPointSummary]


@dataclass
class SectionSummary:
    section_code: str
    section_title: str
    disclosure_count: int
    datapoint_count: int
    disclosures: list[DisclosureSummary]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export GRI catalog summary to JSON and CSV.")
    parser.add_argument(
        "--json-out",
        type=Path,
        default=REPO_ROOT / "artifacts" / "gri" / "gri_catalog_summary.json",
        help="Path to the JSON output file.",
    )
    parser.add_argument(
        "--csv-out",
        type=Path,
        default=REPO_ROOT / "artifacts" / "gri" / "gri_catalog_summary.csv",
        help="Path to the CSV output file.",
    )
    return parser


async def load_summary() -> tuple[dict[str, object], list[dict[str, object]]]:
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as session:
            standard = (
                await session.execute(select(Standard).where(Standard.code == "GRI"))
            ).scalar_one()

            sections = (
                await session.execute(
                    select(StandardSection)
                    .where(
                        StandardSection.standard_id == standard.id,
                        StandardSection.code.is_not(None),
                    )
                    .order_by(StandardSection.sort_order, StandardSection.code)
                )
            ).scalars().all()

            section_summaries: list[SectionSummary] = []
            csv_rows: list[dict[str, object]] = []

            for section in sections:
                disclosures = (
                    await session.execute(
                        select(DisclosureRequirement)
                        .where(DisclosureRequirement.section_id == section.id)
                        .order_by(DisclosureRequirement.sort_order, DisclosureRequirement.code)
                    )
                ).scalars().all()

                disclosure_summaries: list[DisclosureSummary] = []
                section_datapoint_count = 0

                for disclosure in disclosures:
                    items = (
                        await session.execute(
                            select(RequirementItem)
                            .where(
                                RequirementItem.disclosure_requirement_id == disclosure.id,
                                RequirementItem.is_current.is_(True),
                            )
                            .order_by(RequirementItem.sort_order, RequirementItem.item_code, RequirementItem.id)
                        )
                    ).scalars().all()

                    datapoints = [
                        DataPointSummary(
                            item_code=item.item_code,
                            name=item.name,
                            item_type=item.item_type,
                            value_type=item.value_type,
                            unit_code=item.unit_code,
                            sort_order=item.sort_order,
                        )
                        for item in items
                    ]
                    datapoint_count = len(datapoints)
                    section_datapoint_count += datapoint_count

                    disclosure_summaries.append(
                        DisclosureSummary(
                            code=disclosure.code,
                            title=disclosure.title,
                            requirement_type=disclosure.requirement_type,
                            datapoint_count=datapoint_count,
                            datapoints=datapoints,
                        )
                    )

                    if datapoints:
                        for datapoint in datapoints:
                            csv_rows.append(
                                {
                                    "section_code": section.code,
                                    "section_title": section.title,
                                    "disclosure_code": disclosure.code,
                                    "disclosure_title": disclosure.title,
                                    "requirement_type": disclosure.requirement_type,
                                    "datapoint_count_in_disclosure": datapoint_count,
                                    "item_code": datapoint.item_code,
                                    "item_name": datapoint.name,
                                    "item_type": datapoint.item_type,
                                    "value_type": datapoint.value_type,
                                    "unit_code": datapoint.unit_code,
                                    "item_sort_order": datapoint.sort_order,
                                }
                            )
                    else:
                        csv_rows.append(
                            {
                                "section_code": section.code,
                                "section_title": section.title,
                                "disclosure_code": disclosure.code,
                                "disclosure_title": disclosure.title,
                                "requirement_type": disclosure.requirement_type,
                                "datapoint_count_in_disclosure": 0,
                                "item_code": None,
                                "item_name": None,
                                "item_type": None,
                                "value_type": None,
                                "unit_code": None,
                                "item_sort_order": None,
                            }
                        )

                section_summaries.append(
                    SectionSummary(
                        section_code=section.code,
                        section_title=section.title,
                        disclosure_count=len(disclosure_summaries),
                        datapoint_count=section_datapoint_count,
                        disclosures=disclosure_summaries,
                    )
                )

            payload = {
                "standard": {
                    "code": standard.code,
                    "name": standard.name,
                    "version": standard.version,
                },
                "totals": {
                    "section_count": len(section_summaries),
                    "disclosure_count": sum(section.disclosure_count for section in section_summaries),
                    "datapoint_count": sum(section.datapoint_count for section in section_summaries),
                },
                "documents": [asdict(section) for section in section_summaries],
            }

            return payload, csv_rows
    finally:
        await engine.dispose()


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "section_code",
        "section_title",
        "disclosure_code",
        "disclosure_title",
        "requirement_type",
        "datapoint_count_in_disclosure",
        "item_code",
        "item_name",
        "item_type",
        "value_type",
        "unit_code",
        "item_sort_order",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


async def async_main(args: argparse.Namespace) -> int:
    payload, csv_rows = await load_summary()
    write_json(args.json_out, payload)
    write_csv(args.csv_out, csv_rows)

    print(f"JSON: {args.json_out}")
    print(f"CSV:  {args.csv_out}")
    print(
        "Totals:",
        payload["totals"],
    )
    print(f"CSV rows: {len(csv_rows)}")
    return 0


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    return asyncio.run(async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
