from __future__ import annotations

import argparse
import asyncio
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from zipfile import ZipFile

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.domain.catalog import prepare_shared_element_defaults
from app.db.models.mapping import RequirementItemSharedElement
from app.db.models.requirement_item import RequirementItem
from app.db.models.shared_element import SharedElement
from app.db.models.standard import DisclosureRequirement, Standard, StandardSection

WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
DOC_TITLE_RE = re.compile(
    r"^GRI\s+(?P<section_number>\d+):\s+(?P<section_title>.+?)\s+(?P<version>\d{4})(?:\s+Update)?$"
)
DISCLOSURE_RE = re.compile(r"^Disclosure\s+(?P<raw_code>\d+-\d+)\s+(?P<title>.+)$")
DATAPOINT_LINE_RE = re.compile(r'^"?(?P<raw_code>\d{3}-[A-Za-z0-9.-]+):\s*(?P<label>.+?)"?$')


@dataclass
class ParsedDataPoint:
    raw_code: str
    item_code: str
    label: str
    item_type: str
    value_type: str
    unit_code: str | None


@dataclass
class ParsedDisclosure:
    raw_code: str
    code: str
    title: str
    requirement_text: str
    requirement_type: str
    datapoints: list[ParsedDataPoint]
    sort_order: int
    applicability_rule: dict | None = None


@dataclass
class ParsedDocument:
    standard_code: str
    standard_name: str
    standard_version: str
    section_code: str
    section_title: str
    section_sort_order: int
    disclosures: list[ParsedDisclosure]


@dataclass
class ImportStats:
    created_sections: int = 0
    updated_sections: int = 0
    created_disclosures: int = 0
    updated_disclosures: int = 0
    created_items: int = 0
    updated_items: int = 0
    created_shared_elements: int = 0
    updated_shared_elements: int = 0
    created_mappings: int = 0

    def merge(self, other: "ImportStats") -> None:
        self.created_sections += other.created_sections
        self.updated_sections += other.updated_sections
        self.created_disclosures += other.created_disclosures
        self.updated_disclosures += other.updated_disclosures
        self.created_items += other.created_items
        self.updated_items += other.updated_items
        self.created_shared_elements += other.created_shared_elements
        self.updated_shared_elements += other.updated_shared_elements
        self.created_mappings += other.created_mappings


@dataclass
class DocumentRunResult:
    path: Path
    parsed: ParsedDocument
    total_items: int
    stats: ImportStats


def extract_docx_paragraphs(path: Path) -> list[str]:
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))

    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", WORD_NS):
        chunks: list[str] = []
        for node in paragraph.iter():
            if node.tag == "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t":
                chunks.append(node.text or "")
            elif node.tag == "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tab":
                chunks.append("\t")
        text = "".join(chunks).strip()
        if text:
            paragraphs.append(text)
    return paragraphs


def require_index(lines: list[str], predicate, start: int = 0) -> int:
    for idx in range(start, len(lines)):
        if predicate(lines[idx]):
            return idx
    raise ValueError("Expected marker was not found while parsing DOCX")


def is_requirements_marker(line: str) -> bool:
    return line.upper().startswith(("REQUIREMENTS", "REQUIREMENT"))


def marker_index(lines: list[str], marker: str, start: int, end: int) -> int | None:
    if marker.upper() == "REQUIREMENTS":
        for idx in range(start, end):
            if is_requirements_marker(lines[idx]):
                return idx
        return None

    marker_upper = marker.upper()
    for idx in range(start, end):
        if lines[idx].upper().startswith(marker_upper):
            return idx
    return None


def marker_remainder(line: str, marker: str) -> str:
    if marker.upper() == "REQUIREMENTS" and is_requirements_marker(line):
        prefix = "REQUIREMENTS" if line.upper().startswith("REQUIREMENTS") else "REQUIREMENT"
        return line[len(prefix) :].strip(" :-")
    if line.upper().startswith(marker.upper()):
        return line[len(marker) :].strip(" :-")
    return ""


def find_actual_disclosure_indices(lines: list[str], section_number: int) -> list[int]:
    disclosure_indices = []
    for idx, line in enumerate(lines):
        match = DISCLOSURE_RE.match(line)
        if not match:
            continue
        if not match.group("raw_code").startswith(f"{section_number}-"):
            continue
        disclosure_indices.append(idx)
    actual_indices: list[int] = []
    for pos, idx in enumerate(disclosure_indices):
        next_idx = disclosure_indices[pos + 1] if pos + 1 < len(disclosure_indices) else len(lines)
        section_lines = lines[idx + 1 : next_idx]
        has_requirements = any(is_requirements_marker(line) for line in section_lines)
        has_guidance = any(line.upper().startswith("GUIDANCE") for line in section_lines)
        has_datapoint = any(line.upper().startswith("DATAPOINT") for line in section_lines)
        if has_requirements and (has_guidance or has_datapoint):
            actual_indices.append(idx)
    return actual_indices


def collect_datapoints(lines: list[str], start: int, end: int) -> list[tuple[str, str]]:
    raw_datapoints: list[tuple[str, str]] = []
    current_code: str | None = None
    current_label: str | None = None

    for idx in range(start, end):
        candidate = lines[idx].strip()
        if not candidate:
            continue
        if candidate.upper().startswith(("DISCLOSURE ", "GRI ")) or candidate.startswith("Page address:"):
            break

        match = DATAPOINT_LINE_RE.match(candidate)
        if match:
            if current_code is not None and current_label is not None:
                raw_datapoints.append((current_code, " ".join(current_label.split())))
            current_code = match.group("raw_code").strip()
            current_label = match.group("label").strip().strip('"')
            continue

        if current_code is not None and current_label is not None:
            current_label = f"{current_label} {candidate.strip().strip('\"')}"

    if current_code is not None and current_label is not None:
        raw_datapoints.append((current_code, " ".join(current_label.split())))

    return raw_datapoints


def infer_item_shape(label: str) -> tuple[str, str, str | None]:
    normalized = " ".join(label.lower().split())
    if normalized.startswith("how "):
        return "narrative", "text", None
    if normalized.endswith("?") or normalized.startswith(("is ", "are ", "does ", "do ", "whether ")):
        return "attribute", "boolean", None
    if "date" in normalized:
        return "attribute", "date", None
    if "size in hectares" in normalized or "area under restoration" in normalized:
        return "metric", "number", "ha"
    if "percentage" in normalized or "proportion" in normalized:
        return "metric", "number", "%"
    if normalized.startswith(("distance ", "number of ", "quantity ", "amount ", "total ")):
        return "metric", "number", None
    if "size " in normalized and "hectares" not in normalized:
        return "metric", "number", None
    if normalized.startswith(("list ", "type of ", "types of ", "location", "geographic location", "countries or jurisdictions")):
        return "attribute", "text", None
    if normalized.startswith(("description", "explanation", "contextual information", "goals", "indicators", "activities", "products and services")):
        return "narrative", "text", None
    return "attribute", "text", None


def infer_disclosure_type(datapoints: Iterable[ParsedDataPoint]) -> str:
    value_types = {item.value_type for item in datapoints}
    if value_types <= {"number"}:
        return "quantitative"
    if value_types & {"number", "boolean", "date"} and value_types - {"number", "boolean", "date"}:
        return "mixed"
    if value_types & {"number", "boolean", "date"}:
        return "mixed"
    return "qualitative"


def normalize_unique_item_codes(raw_datapoints: list[tuple[str, str]]) -> list[ParsedDataPoint]:
    counts = Counter(raw_code for raw_code, _label in raw_datapoints)
    seen: defaultdict[str, int] = defaultdict(int)
    parsed: list[ParsedDataPoint] = []

    for raw_code, label in raw_datapoints:
        seen[raw_code] += 1
        if counts[raw_code] == 1:
            item_code = f"GRI {raw_code}"
        else:
            item_code = f"GRI {raw_code}.{seen[raw_code]}"
        item_type, value_type, unit_code = infer_item_shape(label)
        parsed.append(
            ParsedDataPoint(
                raw_code=raw_code,
                item_code=item_code,
                label=label,
                item_type=item_type,
                value_type=value_type,
                unit_code=unit_code,
            )
        )
    return parsed


def parse_docx(path: Path) -> ParsedDocument:
    lines = extract_docx_paragraphs(path)
    if not lines:
        raise ValueError(f"{path} is empty")

    title_match = DOC_TITLE_RE.match(lines[0])
    if not title_match:
        raise ValueError(f"Unable to parse GRI title line: {lines[0]!r}")

    section_number = int(title_match.group("section_number"))
    section_title = title_match.group("section_title").strip()
    standard_version = title_match.group("version")

    disclosure_indices = find_actual_disclosure_indices(lines, section_number)
    if not disclosure_indices:
        raise ValueError("Unable to locate the start of disclosure content in the DOCX")

    disclosures_by_code: dict[str, ParsedDisclosure] = {}
    for pos, idx in enumerate(disclosure_indices):
        line = lines[idx]
        disclosure_match = DISCLOSURE_RE.match(line)
        if not disclosure_match:
            raise ValueError(f"Unable to parse disclosure line: {line!r}")

        raw_code = disclosure_match.group("raw_code")
        disclosure_code = f"GRI {raw_code}"
        disclosure_title = disclosure_match.group("title").strip()
        sort_order = int(raw_code.split("-")[1])
        end_idx = disclosure_indices[pos + 1] if pos + 1 < len(disclosure_indices) else len(lines)

        req_idx = marker_index(lines, "REQUIREMENTS", idx + 1, end_idx)
        if req_idx is None:
            raise ValueError(f"Requirements marker not found for {disclosure_code}")
        guidance_idx = marker_index(lines, "GUIDANCE", req_idx + 1, end_idx)
        datapoint_idx = marker_index(lines, "DATAPOINT", req_idx + 1, end_idx)

        requirement_end = min(
            marker for marker in [guidance_idx, datapoint_idx, end_idx] if marker is not None
        )
        requirement_lines: list[str] = []
        requirement_intro = marker_remainder(lines[req_idx], "REQUIREMENTS")
        if requirement_intro:
            requirement_lines.append(requirement_intro)
        requirement_lines.extend(lines[req_idx + 1 : requirement_end])

        raw_datapoints: list[tuple[str, str]] = []
        if datapoint_idx is not None:
            raw_datapoints = [
                (raw_item_code, label)
                for raw_item_code, label in collect_datapoints(lines, datapoint_idx + 1, end_idx)
                if raw_item_code.startswith(f"{section_number}-")
            ]
        datapoints = normalize_unique_item_codes(raw_datapoints)
        disclosures_by_code[disclosure_code] = ParsedDisclosure(
            raw_code=raw_code,
            code=disclosure_code,
            title=disclosure_title,
            requirement_text="\n".join(requirement_lines).strip(),
            requirement_type=infer_disclosure_type(datapoints),
            datapoints=datapoints,
            sort_order=sort_order,
        )

    disclosures = list(disclosures_by_code.values())
    if not disclosures:
        raise ValueError(f"No disclosures were parsed from {path}")

    return ParsedDocument(
        standard_code="GRI",
        standard_name="GRI Standards",
        standard_version=standard_version,
        section_code=f"GRI {section_number}",
        section_title=section_title,
        section_sort_order=section_number,
        disclosures=disclosures,
    )


async def get_or_create_standard(session: AsyncSession, parsed: ParsedDocument) -> Standard:
    standard = (
        await session.execute(select(Standard).where(Standard.code == parsed.standard_code))
    ).scalar_one_or_none()
    if standard:
        return standard

    standard = Standard(
        code=parsed.standard_code,
        name=parsed.standard_name,
        version=parsed.standard_version,
        jurisdiction="Global",
        is_active=True,
    )
    session.add(standard)
    await session.flush()
    return standard


async def upsert_section(
    session: AsyncSession,
    standard_id: int,
    parsed: ParsedDocument,
    stats: ImportStats,
) -> StandardSection:
    section = (
        await session.execute(
            select(StandardSection).where(
                StandardSection.standard_id == standard_id,
                StandardSection.code == parsed.section_code,
            )
        )
    ).scalar_one_or_none()

    if section is None:
        section = StandardSection(
            standard_id=standard_id,
            code=parsed.section_code,
            title=parsed.section_title,
            sort_order=parsed.section_sort_order,
        )
        session.add(section)
        await session.flush()
        stats.created_sections += 1
        return section

    changed = False
    if section.title != parsed.section_title:
        section.title = parsed.section_title
        changed = True
    if section.sort_order != parsed.section_sort_order:
        section.sort_order = parsed.section_sort_order
        changed = True
    if changed:
        await session.flush()
        stats.updated_sections += 1
    return section


async def upsert_disclosure(
    session: AsyncSession,
    standard_id: int,
    section_id: int,
    parsed: ParsedDisclosure,
    stats: ImportStats,
) -> DisclosureRequirement:
    disclosure = (
        await session.execute(
            select(DisclosureRequirement).where(
                DisclosureRequirement.standard_id == standard_id,
                DisclosureRequirement.code == parsed.code,
            )
        )
    ).scalar_one_or_none()

    if disclosure is None:
        disclosure = DisclosureRequirement(
            standard_id=standard_id,
            section_id=section_id,
            code=parsed.code,
            title=parsed.title,
            description=parsed.requirement_text,
            requirement_type=parsed.requirement_type,
            mandatory_level="mandatory",
            applicability_rule=parsed.applicability_rule,
            sort_order=parsed.sort_order,
        )
        session.add(disclosure)
        await session.flush()
        stats.created_disclosures += 1
        return disclosure

    changed = False
    updates = {
        "section_id": section_id,
        "title": parsed.title,
        "description": parsed.requirement_text,
        "requirement_type": parsed.requirement_type,
        "mandatory_level": "mandatory",
        "applicability_rule": parsed.applicability_rule,
        "sort_order": parsed.sort_order,
    }
    for field_name, value in updates.items():
        if getattr(disclosure, field_name) != value:
            setattr(disclosure, field_name, value)
            changed = True
    if changed:
        await session.flush()
        stats.updated_disclosures += 1
    return disclosure


async def upsert_requirement_item(
    session: AsyncSession,
    disclosure_id: int,
    datapoint: ParsedDataPoint,
    sort_order: int,
    stats: ImportStats,
) -> RequirementItem:
    item = (
        await session.execute(
            select(RequirementItem).where(
                RequirementItem.disclosure_requirement_id == disclosure_id,
                RequirementItem.item_code == datapoint.item_code,
                RequirementItem.is_current.is_(True),
            )
        )
    ).scalar_one_or_none()

    if item is None:
        item = RequirementItem(
            disclosure_requirement_id=disclosure_id,
            item_code=datapoint.item_code,
            name=datapoint.label,
            description=datapoint.label,
            item_type=datapoint.item_type,
            value_type=datapoint.value_type,
            unit_code=datapoint.unit_code,
            is_required=True,
            requires_evidence=False,
            cardinality_min=0,
            cardinality_max=None,
            sort_order=sort_order,
        )
        session.add(item)
        await session.flush()
        stats.created_items += 1
        return item

    changed = False
    updates = {
        "name": datapoint.label,
        "description": datapoint.label,
        "item_type": datapoint.item_type,
        "value_type": datapoint.value_type,
        "unit_code": datapoint.unit_code,
        "sort_order": sort_order,
    }
    for field_name, value in updates.items():
        if getattr(item, field_name) != value:
            setattr(item, field_name, value)
            changed = True
    if changed:
        await session.flush()
        stats.updated_items += 1
    return item


def shared_element_code(item_code: str) -> str:
    normalized = re.sub(r"[^A-Z0-9]+", "-", item_code.upper()).strip("-")
    return f"SE-{normalized}"


async def upsert_shared_element(
    session: AsyncSession,
    item: RequirementItem,
    concept_domain: str,
    stats: ImportStats,
) -> SharedElement:
    code = shared_element_code(item.item_code or f"ITEM-{item.id}")
    element = (
        await session.execute(select(SharedElement).where(SharedElement.code == code))
    ).scalar_one_or_none()

    if element is None:
        element = SharedElement(
            code=code,
            name=item.name,
            description=item.description,
            concept_domain=concept_domain,
            default_value_type=item.value_type,
            default_unit_code=item.unit_code,
            **prepare_shared_element_defaults(code=code),
        )
        session.add(element)
        await session.flush()
        stats.created_shared_elements += 1
        return element

    changed = False
    updates = {
        "name": item.name,
        "description": item.description,
        "concept_domain": concept_domain,
        "default_value_type": item.value_type,
        "default_unit_code": item.unit_code,
    }
    for field_name, value in updates.items():
        if getattr(element, field_name) != value:
            setattr(element, field_name, value)
            changed = True
    if changed:
        await session.flush()
        stats.updated_shared_elements += 1
    return element


async def ensure_mapping(
    session: AsyncSession,
    item_id: int,
    shared_element_id: int,
    stats: ImportStats,
) -> None:
    mapping = (
        await session.execute(
            select(RequirementItemSharedElement).where(
                RequirementItemSharedElement.requirement_item_id == item_id,
                RequirementItemSharedElement.shared_element_id == shared_element_id,
                RequirementItemSharedElement.is_current.is_(True),
            )
        )
    ).scalar_one_or_none()
    if mapping is not None:
        return

    session.add(
        RequirementItemSharedElement(
            requirement_item_id=item_id,
            shared_element_id=shared_element_id,
            mapping_type="full",
        )
    )
    await session.flush()
    stats.created_mappings += 1


async def deactivate_stale_requirement_items(
    session: AsyncSession,
    disclosure_id: int,
    active_item_codes: set[str],
) -> None:
    current_items = (
        await session.execute(
            select(RequirementItem).where(
                RequirementItem.disclosure_requirement_id == disclosure_id,
                RequirementItem.is_current.is_(True),
            )
        )
    ).scalars().all()

    stale_items = [item for item in current_items if item.item_code not in active_item_codes]
    if not stale_items:
        return

    stale_item_ids = [item.id for item in stale_items]
    for item in stale_items:
        item.is_current = False

    stale_mappings = (
        await session.execute(
            select(RequirementItemSharedElement).where(
                RequirementItemSharedElement.requirement_item_id.in_(stale_item_ids),
                RequirementItemSharedElement.is_current.is_(True),
            )
        )
    ).scalars().all()
    for mapping in stale_mappings:
        mapping.is_current = False

    await session.flush()


async def import_docx(
    session: AsyncSession,
    parsed: ParsedDocument,
    *,
    with_shared_elements: bool,
) -> ImportStats:
    stats = ImportStats()
    standard = await get_or_create_standard(session, parsed)
    section = await upsert_section(session, standard.id, parsed, stats)
    concept_domain = re.sub(r"[^a-z0-9]+", "_", parsed.section_title.lower()).strip("_")

    for disclosure in parsed.disclosures:
        disclosure_row = await upsert_disclosure(session, standard.id, section.id, disclosure, stats)
        active_item_codes: set[str] = set()
        for sort_order, datapoint in enumerate(disclosure.datapoints, start=1):
            item = await upsert_requirement_item(
                session, disclosure_row.id, datapoint, sort_order, stats
            )
            active_item_codes.add(datapoint.item_code)
            if with_shared_elements:
                element = await upsert_shared_element(session, item, concept_domain, stats)
                await ensure_mapping(session, item.id, element.id, stats)
        await deactivate_stale_requirement_items(session, disclosure_row.id, active_item_codes)

    return stats


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import a GRI topic DOCX into the framework catalog.")
    parser.add_argument(
        "docx_path",
        type=Path,
        help="Path to a GRI DOCX document or a directory of DOCX documents.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist changes. Without this flag, the script runs as a dry-run.",
    )
    parser.add_argument(
        "--no-shared-elements",
        action="store_true",
        help="Skip creating one-to-one shared elements and mappings for imported requirement items.",
    )
    return parser


def iter_docx_paths(path: Path) -> list[Path]:
    if path.is_file():
        if path.suffix.lower() != ".docx":
            raise ValueError(f"Expected a .docx file, got: {path}")
        return [path]

    if path.is_dir():
        docx_paths = sorted(
            child for child in path.iterdir() if child.is_file() and child.suffix.lower() == ".docx"
        )
        if not docx_paths:
            raise ValueError(f"No .docx files found in directory: {path}")
        return docx_paths

    raise ValueError(f"Path does not exist or is not supported: {path}")


async def run_single_import(
    session_factory: async_sessionmaker[AsyncSession],
    path: Path,
    *,
    apply: bool,
    with_shared_elements: bool,
) -> DocumentRunResult:
    parsed = parse_docx(path)
    total_items = sum(len(disclosure.datapoints) for disclosure in parsed.disclosures)

    async with session_factory() as session:
        stats = await import_docx(
            session,
            parsed,
            with_shared_elements=with_shared_elements,
        )
        if apply:
            await session.commit()
        else:
            await session.rollback()

    return DocumentRunResult(
        path=path,
        parsed=parsed,
        total_items=total_items,
        stats=stats,
    )


async def async_main(args: argparse.Namespace) -> int:
    docx_paths = iter_docx_paths(args.docx_path)
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    aggregate_stats = ImportStats()
    failures: list[tuple[Path, str]] = []

    try:
        print(f"Input: {args.docx_path}")
        print(f"Documents queued: {len(docx_paths)}")
        print(f"Mode: {'apply' if args.apply else 'dry-run'}")
        print()

        for index, docx_path in enumerate(docx_paths, start=1):
            print(f"[{index}/{len(docx_paths)}] {docx_path.name}")
            try:
                result = await run_single_import(
                    session_factory,
                    docx_path,
                    apply=args.apply,
                    with_shared_elements=not args.no_shared_elements,
                )
            except Exception as exc:  # noqa: BLE001
                failures.append((docx_path, str(exc)))
                print(f"  ERROR: {exc}")
                print()
                continue

            aggregate_stats.merge(result.stats)
            print(f"  Section:  {result.parsed.section_code} - {result.parsed.section_title}")
            print(f"  Version:  {result.parsed.standard_version}")
            print(f"  Disclosures parsed: {len(result.parsed.disclosures)}")
            print(f"  Requirement items parsed: {result.total_items}")
            print("  Import summary")
            print(
                f"    Sections:         +{result.stats.created_sections} new, "
                f"{result.stats.updated_sections} updated"
            )
            print(
                f"    Disclosures:      +{result.stats.created_disclosures} new, "
                f"{result.stats.updated_disclosures} updated"
            )
            print(
                f"    RequirementItems: +{result.stats.created_items} new, "
                f"{result.stats.updated_items} updated"
            )
            print(
                f"    SharedElements:   +{result.stats.created_shared_elements} new, "
                f"{result.stats.updated_shared_elements} updated"
            )
            print(f"    Mappings:         +{result.stats.created_mappings} new")
            print()

        print("Aggregate summary")
        print(f"  Documents processed: {len(docx_paths) - len(failures)}")
        print(f"  Documents failed:    {len(failures)}")
        print(
            f"  Sections:            +{aggregate_stats.created_sections} new, "
            f"{aggregate_stats.updated_sections} updated"
        )
        print(
            f"  Disclosures:         +{aggregate_stats.created_disclosures} new, "
            f"{aggregate_stats.updated_disclosures} updated"
        )
        print(
            f"  RequirementItems:    +{aggregate_stats.created_items} new, "
            f"{aggregate_stats.updated_items} updated"
        )
        print(
            f"  SharedElements:      +{aggregate_stats.created_shared_elements} new, "
            f"{aggregate_stats.updated_shared_elements} updated"
        )
        print(f"  Mappings:            +{aggregate_stats.created_mappings} new")
        if failures:
            print()
            print("Failures")
            for failed_path, error_message in failures:
                print(f"  - {failed_path.name}: {error_message}")
        return 1 if failures else 0
    finally:
        await engine.dispose()


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    return asyncio.run(async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
