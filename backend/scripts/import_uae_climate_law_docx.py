from __future__ import annotations

import argparse
import asyncio
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.db.models.standard import DisclosureRequirement, Standard, StandardSection
from scripts.import_gri_docx import (
    ImportStats,
    ParsedDataPoint,
    deactivate_stale_requirement_items,
    ensure_mapping,
    extract_docx_paragraphs,
    infer_disclosure_type,
    upsert_requirement_item,
    upsert_shared_element,
)

STANDARD_CODE = "UAE-LAW-11-2024"
STANDARD_NAME = "Federal Decree-Law No. (11) of 2024 on the Reduction of Climate Change Effects"
STANDARD_VERSION = "2024"
STANDARD_JURISDICTION = "United Arab Emirates"


@dataclass(frozen=True)
class RawDataPointSpec:
    label: str
    value_type: str = "text"
    item_type: str = "attribute"
    unit_code: str | None = None


@dataclass(frozen=True)
class LawDisclosureSpec:
    section_code: str
    section_title: str
    section_sort_order: int
    code: str
    title: str
    reference: str
    requirement: str
    datapoints: tuple[RawDataPointSpec, ...]
    concept_domain: str
    mandatory_level: str = "mandatory"
    sort_order: int = 0


def dp(
    label: str,
    *,
    value_type: str = "text",
    item_type: str = "attribute",
    unit_code: str | None = None,
) -> RawDataPointSpec:
    return RawDataPointSpec(
        label=label,
        value_type=value_type,
        item_type=item_type,
        unit_code=unit_code,
    )


LAW_DISCLOSURES: tuple[LawDisclosureSpec, ...] = (
    LawDisclosureSpec(
        section_code="ART6",
        section_title="Measurement, Reporting and Verification (Article 6)",
        section_sort_order=2,
        code="Art.6(1)(a)-1",
        title="Regular GHG emissions measurement and disclosure",
        reference="Art.6(1)(a)",
        requirement=(
            "The organization shall measure and disclose greenhouse gas (GHG) emissions "
            "from its activities on a regular basis using recognized methodologies."
        ),
        concept_domain="ghg_measurement_reporting",
        sort_order=1,
        datapoints=(
            dp("Reporting period"),
            dp("Organizational boundary"),
            dp("Emission scopes (Scope 1, Scope 2, Scope 3)"),
            dp("Emissions (tCO2e)", value_type="number", item_type="metric", unit_code="tCO2e"),
            dp("Methodology used (e.g. GHG Protocol)"),
            dp("Measurement frequency"),
        ),
    ),
    LawDisclosureSpec(
        section_code="ART6",
        section_title="Measurement, Reporting and Verification (Article 6)",
        section_sort_order=2,
        code="Art.6(1)(a)-2",
        title="Comprehensive emissions inventory",
        reference="Art.6(1)(a)",
        requirement=(
            "The organization shall maintain a comprehensive emissions inventory "
            "covering all relevant sources."
        ),
        concept_domain="ghg_measurement_reporting",
        sort_order=2,
        datapoints=(
            dp("Emissions by source (facility or process)"),
            dp("Emissions by gas (CO2, CH4, N2O, etc.)"),
            dp("Total emissions (tCO2e)", value_type="number", item_type="metric", unit_code="tCO2e"),
            dp("Base year emissions (tCO2e)", value_type="number", item_type="metric", unit_code="tCO2e"),
        ),
    ),
    LawDisclosureSpec(
        section_code="ART6",
        section_title="Measurement, Reporting and Verification (Article 6)",
        section_sort_order=2,
        code="Art.6(1)(a)-3",
        title="Emission reduction measures",
        reference="Art.6(1)(a)",
        requirement=(
            "The organization shall implement measures to reduce emissions in line "
            "with regulatory requirements."
        ),
        concept_domain="ghg_reduction_measures",
        sort_order=3,
        datapoints=(
            dp("List of reduction initiatives", item_type="narrative"),
            dp("Initiative type (energy efficiency, renewables, CCUS, etc.)"),
            dp("Emissions reduced (tCO2e)", value_type="number", item_type="metric", unit_code="tCO2e"),
            dp("Implementation status"),
        ),
    ),
    LawDisclosureSpec(
        section_code="ART6",
        section_title="Measurement, Reporting and Verification (Article 6)",
        section_sort_order=2,
        code="Art.6(1)(b)-1",
        title="Disclosure of activity and reduction data",
        reference="Art.6(1)(b)",
        requirement=(
            "The organization shall disclose data on emission-related activities and "
            "reduction measures (current and planned)."
        ),
        concept_domain="ghg_measurement_reporting",
        sort_order=4,
        datapoints=(
            dp("Activity data (fuel use, energy consumption)", item_type="narrative"),
            dp("Current reduction measures", item_type="narrative"),
            dp("Planned measures", item_type="narrative"),
            dp("Expected emissions reduction (tCO2e)", value_type="number", item_type="metric", unit_code="tCO2e"),
            dp("Timeline"),
        ),
    ),
    LawDisclosureSpec(
        section_code="ART6",
        section_title="Measurement, Reporting and Verification (Article 6)",
        section_sort_order=2,
        code="Art.6(1)(b)-2",
        title="Expected outcomes of emission reduction initiatives",
        reference="Art.6(1)(b)",
        requirement=(
            "The organization shall disclose expected outcomes of emission reduction initiatives."
        ),
        concept_domain="ghg_reduction_measures",
        sort_order=5,
        datapoints=(
            dp("Projected emissions reduction (tCO2e)", value_type="number", item_type="metric", unit_code="tCO2e"),
            dp("Target year"),
            dp("Reduction versus baseline (%)", value_type="number", item_type="metric", unit_code="%"),
        ),
    ),
    LawDisclosureSpec(
        section_code="ART6",
        section_title="Measurement, Reporting and Verification (Article 6)",
        section_sort_order=2,
        code="Art.6(1)(c)",
        title="Emissions data retention and accessibility",
        reference="Art.6(1)(c)",
        requirement=(
            "The organization shall retain emissions data and records for a minimum "
            "of five years and ensure accessibility for regulatory inspection."
        ),
        concept_domain="ghg_recordkeeping",
        sort_order=6,
        datapoints=(
            dp("Data retention policy", item_type="narrative"),
            dp("Record storage location"),
            dp("Availability for audit (Y/N)", value_type="boolean"),
            dp("Last update or audit date"),
        ),
    ),
    LawDisclosureSpec(
        section_code="ART6",
        section_title="Measurement, Reporting and Verification (Article 6)",
        section_sort_order=2,
        code="Art.6(2)",
        title="Submission through designated reporting systems",
        reference="Art.6(2)",
        requirement=(
            "The organization shall submit emissions data through designated reporting systems and formats."
        ),
        concept_domain="ghg_submission_systems",
        sort_order=7,
        datapoints=(
            dp("Submission format (template or system)"),
            dp("Submission date"),
            dp("Reporting authority"),
        ),
    ),
    LawDisclosureSpec(
        section_code="ART6",
        section_title="Measurement, Reporting and Verification (Article 6)",
        section_sort_order=2,
        code="Art.6(3)",
        title="Accuracy and verifiability of emissions data",
        reference="Art.6(3)",
        requirement=(
            "The organization shall ensure accuracy and verifiability of emissions data."
        ),
        concept_domain="ghg_verification",
        sort_order=8,
        datapoints=(
            dp("Verification status (internal or external)"),
            dp("Assurance provider"),
            dp("Data validation process", item_type="narrative"),
        ),
    ),
    LawDisclosureSpec(
        section_code="ART6",
        section_title="Measurement, Reporting and Verification (Article 6)",
        section_sort_order=2,
        code="Art.6(4)",
        title="Support national aggregation and analysis",
        reference="Art.6(4)",
        requirement=(
            "The organization shall support aggregation and analysis of emissions data at national level."
        ),
        concept_domain="ghg_submission_systems",
        sort_order=9,
        datapoints=(
            dp("Data completeness (Y/N)", value_type="boolean"),
            dp("Alignment with national inventory"),
        ),
    ),
    LawDisclosureSpec(
        section_code="ART7-3",
        section_title="Climate Adaptation & Loss Reporting (Article 7(3))",
        section_sort_order=3,
        code="Art.7(3)(a)-1",
        title="Economic losses from climate change impacts",
        reference="Art.7(3)(a)",
        requirement=(
            "The organization shall disclose economic losses resulting from climate change impacts."
        ),
        concept_domain="climate_loss_reporting",
        sort_order=1,
        datapoints=(
            dp("Type of event (flood, heatwave, etc.)"),
            dp("Financial loss (AED or USD)", value_type="number", item_type="metric", unit_code="currency"),
            dp("Asset damage value (AED or USD)", value_type="number", item_type="metric", unit_code="currency"),
            dp("Insurance claims (AED or USD)", value_type="number", item_type="metric", unit_code="currency"),
        ),
    ),
    LawDisclosureSpec(
        section_code="ART7-3",
        section_title="Climate Adaptation & Loss Reporting (Article 7(3))",
        section_sort_order=3,
        code="Art.7(3)(a)-2",
        title="Non-economic losses from climate change impacts",
        reference="Art.7(3)(a)",
        requirement=(
            "The organization shall disclose non-economic losses associated with climate change impacts."
        ),
        concept_domain="climate_loss_reporting",
        sort_order=2,
        datapoints=(
            dp("Human impact (injuries, health effects)", item_type="narrative"),
            dp("Environmental damage (biodiversity loss)", item_type="narrative"),
            dp("Operational disruption (downtime)", item_type="narrative"),
        ),
    ),
    LawDisclosureSpec(
        section_code="ART7-3",
        section_title="Climate Adaptation & Loss Reporting (Article 7(3))",
        section_sort_order=3,
        code="Art.7(3)(a)-3",
        title="Climate-related data requested by authorities",
        reference="Art.7(3)(a)",
        requirement=(
            "The organization shall provide climate-related data as requested by authorities."
        ),
        concept_domain="climate_loss_reporting",
        sort_order=3,
        datapoints=(
            dp("Data request type"),
            dp("Submission date"),
            dp("Data category"),
        ),
    ),
    LawDisclosureSpec(
        section_code="ART7-3",
        section_title="Climate Adaptation & Loss Reporting (Article 7(3))",
        section_sort_order=3,
        code="Art.7(3)(b)-1",
        title="Implementation status of adaptation plans",
        reference="Art.7(3)(b)",
        requirement=(
            "The organization shall disclose implementation status of climate adaptation plans."
        ),
        concept_domain="climate_adaptation",
        sort_order=4,
        datapoints=(
            dp("Adaptation plan name"),
            dp("Sector (energy, infrastructure, etc.)"),
            dp("Implementation status (%)", value_type="number", item_type="metric", unit_code="%"),
            dp("Start date"),
            dp("End date"),
        ),
    ),
    LawDisclosureSpec(
        section_code="ART7-3",
        section_title="Climate Adaptation & Loss Reporting (Article 7(3))",
        section_sort_order=3,
        code="Art.7(3)(b)-2",
        title="Adaptation measures for national and international reporting",
        reference="Art.7(3)(b)",
        requirement=(
            "The organization shall report adaptation measures contributing to national "
            "and international climate reporting."
        ),
        concept_domain="climate_adaptation",
        sort_order=5,
        datapoints=(
            dp("List of adaptation measures", item_type="narrative"),
            dp("KPIs (resilience improvement, risk reduction)", item_type="narrative"),
            dp("Alignment with national adaptation plan"),
        ),
    ),
    LawDisclosureSpec(
        section_code="ART7-3",
        section_title="Climate Adaptation & Loss Reporting (Article 7(3))",
        section_sort_order=3,
        code="Art.7(3)(b)-3",
        title="Data for international climate reporting",
        reference="Art.7(3)(b)",
        requirement=(
            "The organization shall provide data required for international reporting "
            "(e.g. UNFCCC)."
        ),
        concept_domain="climate_adaptation",
        sort_order=6,
        datapoints=(
            dp("Reporting cycle"),
            dp("Included in national report (Y/N)", value_type="boolean"),
            dp("Data submission format"),
        ),
    ),
)


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def clean_law_paragraphs(paragraphs: list[str]) -> list[str]:
    cleaned: list[str] = []
    index = 0
    while index < len(paragraphs):
        current = normalize_whitespace(paragraphs[index])
        if not current:
            index += 1
            continue

        if current == ":" and cleaned and index + 1 < len(paragraphs):
            cleaned[-1] = f"{cleaned[-1]}: {normalize_whitespace(paragraphs[index + 1])}"
            index += 2
            continue

        cleaned.append(current)
        index += 1

    return cleaned


def build_intro_blocks(paragraphs: list[str]) -> dict:
    body_md = "\n\n".join(paragraphs)
    return {
        "source_format": "uae_climate_law_docx",
        "source_title": STANDARD_NAME,
        "law_ref": "Full text",
        "content_blocks": [
            {
                "type": "introduction",
                "title": "Full Law Text",
                "paragraphs": paragraphs,
                "items": [],
                "body_md": body_md,
            }
        ],
    }


def build_requirement_blocks(spec: LawDisclosureSpec) -> dict:
    return {
        "source_format": "uae_climate_law_docx",
        "source_title": STANDARD_NAME,
        "law_ref": spec.reference,
        "content_blocks": [
            {
                "type": "requirements",
                "title": "Requirements",
                "paragraphs": [spec.requirement],
                "items": [],
                "body_md": spec.requirement,
            }
        ],
    }


def build_item_code(disclosure_code: str, label: str) -> str:
    return f"{disclosure_code}.{slugify(label)}"


def build_parsed_datapoints(disclosure_code: str, datapoints: tuple[RawDataPointSpec, ...]) -> list[ParsedDataPoint]:
    return [
        ParsedDataPoint(
            raw_code=disclosure_code,
            item_code=build_item_code(disclosure_code, spec.label),
            label=spec.label,
            item_type=spec.item_type,
            value_type=spec.value_type,
            unit_code=spec.unit_code,
        )
        for spec in datapoints
    ]


async def upsert_standard(session: AsyncSession) -> Standard:
    standard = (
        await session.execute(select(Standard).where(Standard.code == STANDARD_CODE))
    ).scalar_one_or_none()

    if standard is None:
        standard = Standard(
            code=STANDARD_CODE,
            name=STANDARD_NAME,
            version=STANDARD_VERSION,
            jurisdiction=STANDARD_JURISDICTION,
            is_active=True,
        )
        session.add(standard)
        await session.flush()
        return standard

    changed = False
    for field_name, value in {
        "name": STANDARD_NAME,
        "version": STANDARD_VERSION,
        "jurisdiction": STANDARD_JURISDICTION,
        "is_active": True,
    }.items():
        if getattr(standard, field_name) != value:
            setattr(standard, field_name, value)
            changed = True
    if changed:
        await session.flush()
    return standard


async def upsert_section(
    session: AsyncSession,
    *,
    standard_id: int,
    code: str,
    title: str,
    sort_order: int,
    parent_section_id: int | None = None,
    stats: ImportStats,
) -> StandardSection:
    section = (
        await session.execute(
            select(StandardSection).where(
                StandardSection.standard_id == standard_id,
                StandardSection.code == code,
            )
        )
    ).scalar_one_or_none()

    if section is None:
        section = StandardSection(
            standard_id=standard_id,
            code=code,
            title=title,
            sort_order=sort_order,
            parent_section_id=parent_section_id,
        )
        session.add(section)
        await session.flush()
        stats.created_sections += 1
        return section

    changed = False
    updates = {
        "title": title,
        "sort_order": sort_order,
        "parent_section_id": parent_section_id,
    }
    for field_name, value in updates.items():
        if getattr(section, field_name) != value:
            setattr(section, field_name, value)
            changed = True
    if changed:
        await session.flush()
        stats.updated_sections += 1
    return section


async def upsert_disclosure(
    session: AsyncSession,
    *,
    standard_id: int,
    section_id: int,
    code: str,
    title: str,
    description: str,
    requirement_type: str,
    mandatory_level: str,
    sort_order: int,
    applicability_rule: dict | None,
    stats: ImportStats,
) -> DisclosureRequirement:
    disclosure = (
        await session.execute(
            select(DisclosureRequirement).where(
                DisclosureRequirement.standard_id == standard_id,
                DisclosureRequirement.code == code,
            )
        )
    ).scalar_one_or_none()

    if disclosure is None:
        disclosure = DisclosureRequirement(
            standard_id=standard_id,
            section_id=section_id,
            code=code,
            title=title,
            description=description,
            requirement_type=requirement_type,
            mandatory_level=mandatory_level,
            applicability_rule=applicability_rule,
            sort_order=sort_order,
        )
        session.add(disclosure)
        await session.flush()
        stats.created_disclosures += 1
        return disclosure

    changed = False
    updates = {
        "section_id": section_id,
        "title": title,
        "description": description,
        "requirement_type": requirement_type,
        "mandatory_level": mandatory_level,
        "applicability_rule": applicability_rule,
        "sort_order": sort_order,
    }
    for field_name, value in updates.items():
        if getattr(disclosure, field_name) != value:
            setattr(disclosure, field_name, value)
            changed = True
    if changed:
        await session.flush()
        stats.updated_disclosures += 1
    return disclosure


async def import_law_standard(
    session: AsyncSession,
    *,
    docx_path: Path,
    with_shared_elements: bool,
) -> tuple[ImportStats, int]:
    stats = ImportStats()
    standard = await upsert_standard(session)

    intro_section = await upsert_section(
        session,
        standard_id=standard.id,
        code="INTRO",
        title="Introduction & Full Law Text",
        sort_order=1,
        stats=stats,
    )

    law_text_paragraphs = clean_law_paragraphs(extract_docx_paragraphs(docx_path))
    intro_disclosure = await upsert_disclosure(
        session,
        standard_id=standard.id,
        section_id=intro_section.id,
        code="LAW-TEXT",
        title="Full law text",
        description="\n\n".join(law_text_paragraphs),
        requirement_type="qualitative",
        mandatory_level="optional",
        sort_order=1,
        applicability_rule=build_intro_blocks(law_text_paragraphs),
        stats=stats,
    )
    await deactivate_stale_requirement_items(session, intro_disclosure.id, set())

    section_ids: dict[str, int] = {"INTRO": intro_section.id}
    total_items = 0

    for disclosure_spec in LAW_DISCLOSURES:
        if disclosure_spec.section_code not in section_ids:
            section = await upsert_section(
                session,
                standard_id=standard.id,
                code=disclosure_spec.section_code,
                title=disclosure_spec.section_title,
                sort_order=disclosure_spec.section_sort_order,
                stats=stats,
            )
            section_ids[disclosure_spec.section_code] = section.id

        parsed_datapoints = build_parsed_datapoints(disclosure_spec.code, disclosure_spec.datapoints)
        total_items += len(parsed_datapoints)
        disclosure = await upsert_disclosure(
            session,
            standard_id=standard.id,
            section_id=section_ids[disclosure_spec.section_code],
            code=disclosure_spec.code,
            title=disclosure_spec.title,
            description=disclosure_spec.requirement,
            requirement_type=infer_disclosure_type(parsed_datapoints),
            mandatory_level=disclosure_spec.mandatory_level,
            sort_order=disclosure_spec.sort_order,
            applicability_rule=build_requirement_blocks(disclosure_spec),
            stats=stats,
        )

        active_item_codes: set[str] = set()
        for item_sort_order, datapoint in enumerate(parsed_datapoints, start=1):
            item = await upsert_requirement_item(
                session,
                disclosure.id,
                datapoint,
                item_sort_order,
                stats,
            )
            active_item_codes.add(datapoint.item_code)
            if with_shared_elements:
                element = await upsert_shared_element(
                    session,
                    item,
                    disclosure_spec.concept_domain,
                    stats,
                )
                await ensure_mapping(session, item.id, element.id, stats)
        await deactivate_stale_requirement_items(session, disclosure.id, active_item_codes)

    return stats, total_items


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import UAE Federal Decree-Law No. (11) of 2024 as a custom standard."
    )
    parser.add_argument(
        "docx_path",
        type=Path,
        help="Path to the law DOCX document.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist changes. Without this flag, the script runs as a dry-run.",
    )
    parser.add_argument(
        "--no-shared-elements",
        action="store_true",
        help="Skip shared element and mapping creation.",
    )
    return parser


async def async_main(args: argparse.Namespace) -> int:
    if not args.docx_path.exists():
        print(f"ERROR: file not found: {args.docx_path}")
        return 1

    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as session:
            stats, total_items = await import_law_standard(
                session,
                docx_path=args.docx_path,
                with_shared_elements=not args.no_shared_elements,
            )
            if args.apply:
                await session.commit()
            else:
                await session.rollback()
    finally:
        await engine.dispose()

    print(f"Mode: {'apply' if args.apply else 'dry-run'}")
    print(f"Standard: {STANDARD_CODE} - {STANDARD_NAME}")
    print("Sections:")
    print("  - INTRO: Introduction & Full Law Text")
    print("  - ART6: Measurement, Reporting and Verification (Article 6)")
    print("  - ART7-3: Climate Adaptation & Loss Reporting (Article 7(3))")
    print(f"Disclosures: {len(LAW_DISCLOSURES) + 1}")
    print(f"Requirement items: {total_items}")
    print("Import summary")
    print(f"  Sections:         +{stats.created_sections} new, {stats.updated_sections} updated")
    print(f"  Disclosures:      +{stats.created_disclosures} new, {stats.updated_disclosures} updated")
    print(f"  RequirementItems: +{stats.created_items} new, {stats.updated_items} updated")
    print(
        f"  SharedElements:   +{stats.created_shared_elements} new, "
        f"{stats.updated_shared_elements} updated"
    )
    print(f"  Mappings:         +{stats.created_mappings} new")
    return 0


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    return asyncio.run(async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
