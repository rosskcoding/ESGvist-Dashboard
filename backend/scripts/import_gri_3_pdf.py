from __future__ import annotations

import argparse
import asyncio
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from scripts.import_gri_2_pdf import (
    GuidanceSection,
    build_disclosure_description,
    expand_leaf_clause,
    extract_pdf_lines,
    find_marker_index,
    marker_remainder,
    normalize_text,
    parse_requirement_clauses,
    serialize_clause,
    strip_numeric_citations,
)
from scripts.import_gri_docx import (
    ImportStats,
    ParsedDataPoint,
    ParsedDisclosure,
    ParsedDocument,
    deactivate_stale_requirement_items,
    ensure_mapping,
    get_or_create_standard,
    infer_disclosure_type,
    infer_item_shape,
    upsert_disclosure,
    upsert_requirement_item,
    upsert_section,
    upsert_shared_element,
)

PDF_TITLE_RE = re.compile(r"^GRI\s+3:\s+Material Topics\s+2021$")
DISCLOSURE_RE = re.compile(r"^Disclosure\s+(?P<raw_code>3-[123])\s+(?P<title>.+)$")
PAGE_HEADER_RE = re.compile(r"^\d+\s+GRI 3:\s+Material Topics\s+2021$")
BULLET_RE = re.compile(r"^(?P<indent>\s*)(?P<marker>•|-)\s+(?P<text>.+)$")


@dataclass
class PdfRunResult:
    path: Path
    parsed: ParsedDocument
    total_items: int
    stats: ImportStats


def is_page_noise(text: str) -> bool:
    return (
        not text
        or text == "GRI 3: Material Topics 2021"
        or PAGE_HEADER_RE.match(text) is not None
    )


def find_actual_disclosure_indices(lines: list[str]) -> list[int]:
    candidates = [idx for idx, line in enumerate(lines) if DISCLOSURE_RE.match(line.strip())]
    actual: list[int] = []
    for pos, idx in enumerate(candidates):
        next_idx = candidates[pos + 1] if pos + 1 < len(candidates) else len(lines)
        window_end = min(next_idx, idx + 90)
        if any(lines[cursor].strip().startswith("REQUIREMENTS") for cursor in range(idx + 1, window_end)):
            actual.append(idx)
    return actual


def parse_disclosure_heading(lines: list[str], start: int, end: int) -> tuple[str, str, str | None]:
    match = DISCLOSURE_RE.match(lines[start].strip())
    if not match:
        raise ValueError(f"Unable to parse disclosure heading: {lines[start]!r}")

    raw_code = match.group("raw_code")
    title_parts = [normalize_text(match.group("title"))]
    preface: str | None = None

    for idx in range(start + 1, end):
        stripped = normalize_text(lines[idx])
        if is_page_noise(stripped):
            continue
        if stripped.endswith("shall:"):
            preface = stripped
            break
        if stripped.startswith(("REQUIREMENTS", "GUIDANCE")):
            break
        if stripped:
            title_parts.append(stripped)

    return raw_code, " ".join(title_parts).strip(), preface


def normalize_datapoint_text(text: str) -> str:
    normalized = normalize_text(text).rstrip(" ;.:")
    if normalized.endswith(", including"):
        return normalized[: -len(", including")].rstrip()
    if normalized.endswith(" including"):
        return normalized[: -len(" including")].rstrip()
    return normalized


def iter_datapoint_clauses(clauses) -> list[tuple[str, str]]:
    flattened: list[tuple[str, str]] = []

    def walk(clause) -> None:
        flattened.append((clause.code, normalize_datapoint_text(clause.text)))
        for child in clause.children:
            walk(child)

    for clause in clauses:
        walk(clause)
    return flattened


def consume_bullet_item(lines: list[str], start: int, end: int) -> tuple[str, int]:
    match = BULLET_RE.match(lines[start].rstrip())
    if not match:
        raise ValueError(f"Expected bullet line at index {start}")

    marker = match.group("marker")
    indent = 1 if marker == "-" else 0
    parts = [strip_numeric_citations(match.group("text").strip())]
    idx = start + 1

    while idx < end:
        stripped = lines[idx].rstrip()
        compact = stripped.strip()
        if is_page_noise(compact):
            idx += 1
            continue
        if not compact:
            idx += 1
            break
        if BULLET_RE.match(stripped) or compact.startswith(("Guidance to ", "Disclosure ", "REQUIREMENTS", "GUIDANCE")):
            break
        parts.append(strip_numeric_citations(compact))
        idx += 1

    bullet = f'{"  " * indent}- {normalize_text(" ".join(parts))}'
    return bullet, idx


def consume_bullet_block(lines: list[str], start: int, end: int) -> tuple[str, int]:
    bullet_lines: list[str] = []
    idx = start
    while idx < end:
        stripped = lines[idx].rstrip()
        compact = stripped.strip()
        if is_page_noise(compact):
            idx += 1
            continue
        if not compact:
            idx += 1
            if bullet_lines:
                break
            continue
        if not BULLET_RE.match(stripped):
            break
        bullet_line, idx = consume_bullet_item(lines, idx, end)
        bullet_lines.append(bullet_line)
    return "\n".join(bullet_lines).strip(), idx


def parse_guidance_sections(guidance_lines: list[str]) -> list[GuidanceSection]:
    sections: list[GuidanceSection] = []
    current = GuidanceSection(heading=None, chunks=[])
    paragraph_parts: list[str] = []
    idx = 0

    def flush_paragraph() -> None:
        nonlocal paragraph_parts
        if not paragraph_parts:
            return
        current.chunks.append(normalize_text(" ".join(paragraph_parts)))
        paragraph_parts = []

    while idx < len(guidance_lines):
        stripped = guidance_lines[idx].rstrip()
        compact = stripped.strip()
        if is_page_noise(compact):
            flush_paragraph()
            idx += 1
            continue
        if not compact:
            flush_paragraph()
            idx += 1
            continue
        if compact.startswith("Guidance to "):
            flush_paragraph()
            if current.heading or current.chunks:
                sections.append(current)
            current = GuidanceSection(heading=strip_numeric_citations(compact), chunks=[])
            idx += 1
            continue
        if BULLET_RE.match(stripped):
            flush_paragraph()
            bullet_block, idx = consume_bullet_block(guidance_lines, idx, len(guidance_lines))
            if bullet_block:
                current.chunks.append(bullet_block)
            continue

        cleaned = strip_numeric_citations(compact)
        if cleaned:
            paragraph_parts.append(cleaned)
        idx += 1

    flush_paragraph()
    if current.heading or current.chunks:
        sections.append(current)

    return sections


def guidance_sections_to_markdown(sections: list[GuidanceSection]) -> str:
    parts: list[str] = []
    for section in sections:
        if section.heading:
            parts.append(section.heading)
        parts.extend(chunk for chunk in section.chunks if chunk)
    return "\n\n".join(parts).strip()


def parse_disclosure(lines: list[str], start: int, end: int) -> ParsedDisclosure:
    raw_code, title, heading_preface = parse_disclosure_heading(lines, start, end)

    req_idx = find_marker_index(lines, "REQUIREMENT", start + 1, end)
    if req_idx is None:
        raise ValueError(f"Requirements marker not found for Disclosure {raw_code}")

    guidance_idx = find_marker_index(lines, "GUIDANCE", req_idx + 1, end)
    requirement_end = guidance_idx if guidance_idx is not None else end

    requirement_lines: list[str] = []
    if heading_preface:
        requirement_lines.append(heading_preface)
    requirement_remainder = marker_remainder(lines[req_idx], "REQUIREMENT")
    if requirement_remainder:
        requirement_lines.append(requirement_remainder)
    requirement_lines.extend(lines[req_idx + 1 : requirement_end])

    guidance_lines: list[str] = []
    if guidance_idx is not None:
        guidance_remainder = marker_remainder(lines[guidance_idx], "GUIDANCE")
        if guidance_remainder:
            guidance_lines.append(guidance_remainder)
        guidance_lines.extend(lines[guidance_idx + 1 : end])

    requirement_preface_lines, clauses = parse_requirement_clauses(
        requirement_lines,
        raw_code=raw_code,
    )

    clause_nodes = iter_datapoint_clauses(clauses)
    datapoint_nodes = [
        expanded_node
        for clause_code, clause_text in clause_nodes
        for expanded_node in expand_leaf_clause(clause_code, clause_text)
    ]

    datapoints: list[ParsedDataPoint] = []
    seen_item_codes: set[str] = set()
    for clause_code, clause_text in datapoint_nodes:
        item_code = f"GRI {clause_code}"
        if item_code in seen_item_codes:
            continue
        seen_item_codes.add(item_code)
        item_type, value_type, unit_code = infer_item_shape(clause_text)
        datapoints.append(
            ParsedDataPoint(
                raw_code=clause_code,
                item_code=item_code,
                label=clause_text,
                item_type=item_type,
                value_type=value_type,
                unit_code=unit_code,
            )
        )

    guidance_sections = parse_guidance_sections(guidance_lines)

    requirement_markdown_parts: list[str] = []
    if requirement_preface_lines:
        requirement_markdown_parts.append("\n".join(requirement_preface_lines))
    requirement_markdown_parts.extend(
        [
            "\n".join(
                f"- {code} {label}"
                for code, label in clause_nodes
            )
        ]
    )
    requirements_body = "\n".join(part for part in requirement_markdown_parts if part).strip()
    guidance_body = guidance_sections_to_markdown(guidance_sections)

    content_blocks = [
        {
            "type": "requirements",
            "title": "Requirements",
            "body_md": requirements_body or None,
            "paragraphs": [],
            "items": [datapoint.label for datapoint in datapoints],
            "metadata": {
                "preface": requirement_preface_lines,
                "requirement_tree": [serialize_clause(clause) for clause in clauses],
            },
        }
    ]
    if guidance_body:
        content_blocks.append(
            {
                "type": "guidance",
                "title": "Guidance",
                "body_md": guidance_body,
                "paragraphs": [],
                "items": [],
                "metadata": {
                    "sections": [asdict(section) for section in guidance_sections],
                },
            }
        )

    applicability_rule = {
        "source_format": "gri_3_pdf_v1",
        "section_code": "GRI 3",
        "raw_code": raw_code,
        "content_blocks": content_blocks,
        "data_points": [
            {
                "item_code": datapoint.item_code,
                "label": datapoint.label,
                "item_type": datapoint.item_type,
                "value_type": datapoint.value_type,
                "unit_code": datapoint.unit_code,
            }
            for datapoint in datapoints
        ],
    }

    return ParsedDisclosure(
        raw_code=raw_code,
        code=f"GRI {raw_code}",
        title=title,
        requirement_text=build_disclosure_description(content_blocks),
        requirement_type=infer_disclosure_type(datapoints),
        datapoints=datapoints,
        sort_order=int(raw_code.split("-")[1]),
        applicability_rule=applicability_rule,
    )


def parse_pdf(path: Path) -> ParsedDocument:
    lines = extract_pdf_lines(path)
    if not any(PDF_TITLE_RE.match(line.strip()) for line in lines[:8]):
        raise ValueError("Unable to identify GRI 3 title in the PDF")

    disclosure_indices = find_actual_disclosure_indices(lines)
    if len(disclosure_indices) != 3:
        raise ValueError(f"Expected 3 disclosures for GRI 3, parsed {len(disclosure_indices)}")

    disclosures = [
        parse_disclosure(
            lines,
            idx,
            disclosure_indices[pos + 1] if pos + 1 < len(disclosure_indices) else len(lines),
        )
        for pos, idx in enumerate(disclosure_indices)
    ]

    return ParsedDocument(
        standard_code="GRI",
        standard_name="GRI Standards",
        standard_version="2021",
        section_code="GRI 3",
        section_title="Material Topics",
        section_sort_order=3,
        disclosures=disclosures,
    )


async def import_gri_3_pdf(
    session: AsyncSession,
    parsed: ParsedDocument,
    *,
    with_shared_elements: bool,
) -> ImportStats:
    stats = ImportStats()
    standard = await get_or_create_standard(session, parsed)
    section = await upsert_section(session, standard.id, parsed, stats)
    concept_domain = "material_topics"

    for disclosure in parsed.disclosures:
        disclosure_row = await upsert_disclosure(
            session,
            standard.id,
            section.id,
            disclosure,
            stats,
        )

        active_item_codes: set[str] = set()
        for sort_order, datapoint in enumerate(disclosure.datapoints, start=1):
            item = await upsert_requirement_item(
                session,
                disclosure_row.id,
                datapoint,
                sort_order,
                stats,
            )
            active_item_codes.add(datapoint.item_code)

            if with_shared_elements:
                element = await upsert_shared_element(session, item, concept_domain, stats)
                await ensure_mapping(session, item.id, element.id, stats)

        await deactivate_stale_requirement_items(session, disclosure_row.id, active_item_codes)

    return stats


async def run_import(
    path: Path,
    *,
    apply: bool,
    with_shared_elements: bool,
) -> PdfRunResult:
    parsed = parse_pdf(path)
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as session:
            stats = await import_gri_3_pdf(
                session,
                parsed,
                with_shared_elements=with_shared_elements,
            )
            if apply:
                await session.commit()
            else:
                await session.rollback()
    finally:
        await engine.dispose()

    return PdfRunResult(
        path=path,
        parsed=parsed,
        total_items=sum(len(disclosure.datapoints) for disclosure in parsed.disclosures),
        stats=stats,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import GRI 3 Material Topics 2021 from PDF.")
    parser.add_argument("pdf_path", type=Path, help="Path to the GRI 3 PDF file.")
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


async def async_main(args: argparse.Namespace) -> int:
    result = await run_import(
        args.pdf_path,
        apply=args.apply,
        with_shared_elements=not args.no_shared_elements,
    )

    print(f"Input:       {result.path}")
    print(f"Mode:        {'apply' if args.apply else 'dry-run'}")
    print(f"Section:     {result.parsed.section_code} - {result.parsed.section_title}")
    print(f"Disclosures: {len(result.parsed.disclosures)}")
    print(f"DataPoints:  {result.total_items}")
    print("Import summary")
    print(
        f"  Sections:         +{result.stats.created_sections} new, "
        f"{result.stats.updated_sections} updated"
    )
    print(
        f"  Disclosures:      +{result.stats.created_disclosures} new, "
        f"{result.stats.updated_disclosures} updated"
    )
    print(
        f"  RequirementItems: +{result.stats.created_items} new, "
        f"{result.stats.updated_items} updated"
    )
    print(
        f"  SharedElements:   +{result.stats.created_shared_elements} new, "
        f"{result.stats.updated_shared_elements} updated"
    )
    print(f"  Mappings:         +{result.stats.created_mappings} new")
    return 0


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    return asyncio.run(async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
