from __future__ import annotations

import argparse
import asyncio
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.db.models.standard import StandardSection
from scripts.import_gri_docx import (
    ImportStats,
    ParsedDataPoint,
    ParsedDisclosure,
    deactivate_stale_requirement_items,
    ensure_mapping,
    get_or_create_standard,
    infer_disclosure_type,
    infer_item_shape,
    iter_docx_paths,
    upsert_disclosure,
    upsert_requirement_item,
    upsert_shared_element,
)

WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
DOC_TITLE_RE = re.compile(
    r"^GRI\s+(?P<section_number>\d+):\s+(?P<section_title>.+?)\s+(?P<version>\d{4})$"
)
TOPIC_RE = re.compile(r"^Topic\s+(?P<topic_code>\d+\.\d+)\s+(?P<title>.+)$")
SECTOR_REF_RE = re.compile(r"^\d+\.\d+\.\d+$")
DISCLOSURE_LINE_RE = re.compile(r"^Disclosure\s+(?P<code>.+)$")

GROUP_TITLES = {
    "management": "Management of the topic",
    "topic_standard_disclosures": "Topic standard disclosures",
    "additional_sector_disclosures": "Additional sector disclosures",
}
GROUP_SORT_ORDERS = {
    "management": 10,
    "topic_standard_disclosures": 20,
    "additional_sector_disclosures": 30,
}
GROUP_SUFFIXES = {
    "management": "MGMT",
    "topic_standard_disclosures": "STD",
    "additional_sector_disclosures": "ADDL",
}


@dataclass
class TableBlock:
    rows: list[list[list[str]]]


@dataclass
class ParagraphBlock:
    text: str


DocBlock = TableBlock | ParagraphBlock


@dataclass
class SectoralEntry:
    group_key: str
    sector_ref_code: str
    standard_label: str | None
    paragraphs: list[str]


@dataclass
class SectoralTopic:
    topic_code: str
    title: str
    sort_order: int
    entries: list[SectoralEntry] = field(default_factory=list)


@dataclass
class SectoralDocument:
    standard_code: str
    standard_name: str
    standard_version: str
    topics: list[SectoralTopic]


@dataclass
class DocumentRunResult:
    path: Path
    parsed: SectoralDocument
    disclosure_count: int
    item_count: int
    stats: ImportStats


def paragraph_text(paragraph: ET.Element) -> str:
    chunks: list[str] = []
    for node in paragraph.iter():
        tag = node.tag.rsplit("}", 1)[-1]
        if tag == "t":
            chunks.append(node.text or "")
        elif tag == "tab":
            chunks.append("\t")
    return "".join(chunks).strip()


def cell_paragraphs(cell: ET.Element) -> list[str]:
    texts: list[str] = []
    for paragraph in cell.findall(".//w:p", WORD_NS):
        text = paragraph_text(paragraph)
        if text:
            texts.append(text)
    return texts


def extract_docx_blocks(path: Path) -> list[DocBlock]:
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))

    body = root.find("w:body", WORD_NS)
    if body is None:
        return []

    blocks: list[DocBlock] = []
    for child in body:
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            text = paragraph_text(child)
            if text:
                blocks.append(ParagraphBlock(text=text))
        elif tag == "tbl":
            rows: list[list[list[str]]] = []
            for row in child.findall("w:tr", WORD_NS):
                cells = [cell_paragraphs(cell) for cell in row.findall("w:tc", WORD_NS)]
                if any(cell for cell in cells):
                    rows.append(cells)
            if rows:
                blocks.append(TableBlock(rows=rows))
    return blocks


def is_topic_paragraph(block: DocBlock) -> re.Match[str] | None:
    if isinstance(block, ParagraphBlock):
        return TOPIC_RE.match(block.text)
    return None


def next_nonempty_block(blocks: list[DocBlock], start_idx: int) -> DocBlock | None:
    for idx in range(start_idx + 1, len(blocks)):
        block = blocks[idx]
        if isinstance(block, ParagraphBlock) and not block.text.strip():
            continue
        return block
    return None


def is_reporting_table(table: TableBlock) -> bool:
    flattened = [" ".join(cell) for row in table.rows for cell in row]
    if any("SECTOR STANDARD REF #" in value for value in flattened):
        return True
    if any(SECTOR_REF_RE.match(value.strip()) for value in flattened):
        return True
    if any("Additional Sector Disclosures" in value or "Additional sector disclosures" in value for value in flattened):
        return True
    if any("Management of the Topic" in value or "Management of the topic" in value for value in flattened):
        return True
    if any("Topic Standard Disclosures" in value or "Topic Standard disclosures" in value for value in flattened):
        return True
    return False


def normalize_group_label(text: str) -> str | None:
    value = " ".join(text.split()).strip().lower()
    if value == "management of the topic":
        return "management"
    if value == "topic standard disclosures":
        return "topic_standard_disclosures"
    if value == "additional sector disclosures":
        return "additional_sector_disclosures"
    return None


def extract_sector_ref(cells: list[list[str]]) -> str | None:
    for cell in cells:
        for paragraph in cell:
            text = " ".join(paragraph.split())
            if SECTOR_REF_RE.match(text):
                return text
    return None


def clean_cell_text(paragraphs: list[str]) -> str:
    return " ".join(" ".join(p.split()) for p in paragraphs if p.strip()).strip()


def normalize_text(text: str) -> str:
    return " ".join(text.split()).strip()


def normalize_lines(paragraphs: list[str]) -> list[str]:
    return [normalize_text(paragraph) for paragraph in paragraphs if paragraph.strip()]


def markdown_bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items if item.strip())


def make_content_block(
    *,
    block_type: str,
    title: str,
    paragraphs: list[str] | None = None,
    items: list[str] | None = None,
    metadata: dict | None = None,
) -> dict:
    normalized_paragraphs = normalize_lines(paragraphs or [])
    normalized_items = [normalize_text(item) for item in (items or []) if item.strip()]
    body_parts: list[str] = []
    if normalized_paragraphs:
        body_parts.append("\n".join(normalized_paragraphs))
    if normalized_items:
        body_parts.append(markdown_bullets(normalized_items))

    return {
        "type": block_type,
        "title": title,
        "body_md": "\n\n".join(part for part in body_parts if part).strip() or None,
        "paragraphs": normalized_paragraphs,
        "items": normalized_items,
        "metadata": metadata or {},
    }


def build_disclosure_description(blocks: list[dict]) -> str:
    visible_types = {
        "reference_standard",
        "reference_disclosure",
        "requirements",
        "recommendations",
        "guidance",
    }
    sections: list[str] = []
    for block in blocks:
        if block["type"] not in visible_types:
            continue
        body = (block.get("body_md") or "").strip()
        if not body:
            continue
        sections.append(f'{block["title"]}\n{body}')
    return "\n\n".join(sections).strip()


def parse_topic_entries(tables: list[TableBlock]) -> list[SectoralEntry]:
    entries: list[SectoralEntry] = []
    current_group: str | None = None
    last_entry: SectoralEntry | None = None

    for table in tables:
        for row in table.rows:
            cells = row + [[]] * (3 - len(row))
            first_cell = clean_cell_text(cells[0])
            second_cell = clean_cell_text(cells[1])
            third_cell = clean_cell_text(cells[2])

            if first_cell == "STANDARD" and second_cell == "DISCLOSURE":
                last_entry = None
                continue

            group_key = normalize_group_label(first_cell or second_cell or third_cell)
            if group_key:
                current_group = group_key
                last_entry = None
                continue

            sector_ref = extract_sector_ref(cells)
            if sector_ref is None and last_entry is not None:
                continuation = cells[1] if cells[1] else cells[0]
                if continuation:
                    last_entry.paragraphs.extend(continuation)
                continue

            if sector_ref is None or current_group is None:
                continue

            if current_group == "additional_sector_disclosures":
                paragraphs = cells[0]
                standard_label = None
            else:
                paragraphs = cells[1]
                standard_label = clean_cell_text(cells[0]) or None

            entry = SectoralEntry(
                group_key=current_group,
                sector_ref_code=sector_ref,
                standard_label=standard_label,
                paragraphs=list(paragraphs),
            )
            entries.append(entry)
            last_entry = entry

    return entries


def alpha_token(index: int) -> str:
    token = ""
    current = index
    while current > 0:
        current -= 1
        token = chr(ord("a") + (current % 26)) + token
        current //= 26
    return token


def clean_bullet_prefix(text: str) -> tuple[str, bool]:
    stripped = text.strip()
    for prefix in ("•", "-", "–"):
        if stripped.startswith(prefix):
            return stripped[len(prefix) :].strip(), True
    return stripped, False


def extract_items_from_additional_recommendations(paragraphs: list[str]) -> list[str]:
    items: list[str] = []
    prefix_parts: list[str] = []
    current_item: str | None = None

    for paragraph in paragraphs:
        cleaned, is_bullet = clean_bullet_prefix(paragraph)
        if is_bullet:
            if current_item is not None:
                items.append(current_item)
            text = cleaned
            if prefix_parts:
                text = f'{" ".join(prefix_parts)} {text}'.strip()
                prefix_parts = []
            current_item = text
        else:
            if current_item is not None:
                current_item = f"{current_item} {cleaned}".strip()
            else:
                prefix_parts.append(cleaned)

    if current_item is not None:
        items.append(current_item)
    elif prefix_parts:
        items.append(" ".join(prefix_parts))

    return [" ".join(item.split()) for item in items if item.strip()]


def extract_items_from_additional_disclosure(paragraphs: list[str]) -> tuple[str, list[str]]:
    cleaned_paragraphs = [p.strip() for p in paragraphs if p.strip()]
    if not cleaned_paragraphs:
        return "", []

    title = cleaned_paragraphs[0].rstrip(":")
    tail = cleaned_paragraphs[1:]

    bullet_items: list[str] = []
    current_item: str | None = None
    for paragraph in tail:
        cleaned, is_bullet = clean_bullet_prefix(paragraph)
        if is_bullet:
            if current_item is not None:
                bullet_items.append(current_item)
            current_item = cleaned
        else:
            if current_item is not None:
                current_item = f"{current_item} {cleaned}".strip()
            else:
                title = f"{title} {cleaned}".strip()

    if current_item is not None:
        bullet_items.append(current_item)

    if bullet_items:
        return title, [" ".join(item.split()) for item in bullet_items if item.strip()]

    return title, [" ".join(title.split())]


def parse_entry(entry: SectoralEntry, *, topic_code: str, topic_title: str) -> ParsedDisclosure:
    paragraphs = normalize_lines(entry.paragraphs)
    title = ""
    item_texts: list[str] = []
    content_blocks: list[dict] = []

    if entry.group_key in {"management", "topic_standard_disclosures"}:
        source_line = next((p for p in paragraphs if p.startswith("Disclosure ")), "")
        title = source_line[len("Disclosure ") :].strip() if source_line else paragraphs[0]
        marker_idx = next(
            (idx for idx, p in enumerate(paragraphs) if p.lower().startswith("additional sector recommendations")),
            None,
        )
        if marker_idx is not None:
            item_texts = extract_items_from_additional_recommendations(paragraphs[marker_idx + 1 :])
        if entry.standard_label:
            content_blocks.append(
                make_content_block(
                    block_type="reference_standard",
                    title="Reference standard",
                    paragraphs=[entry.standard_label],
                )
            )
        content_blocks.append(
            make_content_block(
                block_type="reference_disclosure",
                title="Reference disclosure",
                paragraphs=[title],
            )
        )
        if item_texts:
            content_blocks.append(
                make_content_block(
                    block_type="recommendations",
                    title="Additional sector recommendations",
                    items=item_texts,
                )
            )
    else:
        title, item_texts = extract_items_from_additional_disclosure(paragraphs)
        requirement_paragraphs: list[str] = []
        for paragraph in paragraphs:
            cleaned, is_bullet = clean_bullet_prefix(paragraph)
            if is_bullet:
                continue
            requirement_paragraphs.append(normalize_text(cleaned))
        content_blocks.append(
            make_content_block(
                block_type="requirements",
                title="Requirements",
                paragraphs=requirement_paragraphs,
            )
        )

    datapoints: list[ParsedDataPoint] = []
    for idx, item_text in enumerate(item_texts, start=1):
        item_type, value_type, unit_code = infer_item_shape(item_text)
        datapoints.append(
            ParsedDataPoint(
                raw_code=f"{entry.sector_ref_code}-{alpha_token(idx)}",
                item_code=f"GRI {entry.sector_ref_code}-{alpha_token(idx)}",
                label=item_text,
                item_type=item_type,
                value_type=value_type,
                unit_code=unit_code,
            )
        )

    if datapoints:
        content_blocks.append(
            make_content_block(
                block_type="data_points",
                title="Data points",
                items=[datapoint.label for datapoint in datapoints],
            )
        )

    applicability_rule = {
        "source_format": "gri_sectoral_docx_v2",
        "group_key": entry.group_key,
        "group_title": GROUP_TITLES[entry.group_key],
        "sector_ref_code": entry.sector_ref_code,
        "topic": {
            "code": topic_code,
            "title": topic_title,
        },
        "reference_standard": entry.standard_label,
        "raw_paragraphs": paragraphs,
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
        raw_code=entry.sector_ref_code,
        code=f"GRI {entry.sector_ref_code}",
        title=title,
        requirement_text=build_disclosure_description(content_blocks),
        requirement_type=infer_disclosure_type(datapoints),
        datapoints=datapoints,
        sort_order=int(entry.sector_ref_code.split(".")[-1]),
        applicability_rule=applicability_rule,
    )


def parse_docx(path: Path) -> SectoralDocument:
    blocks = extract_docx_blocks(path)
    if not blocks or not isinstance(blocks[0], ParagraphBlock):
        raise ValueError(f"Unable to parse title block from {path}")

    title_match = DOC_TITLE_RE.match(blocks[0].text)
    if not title_match:
        raise ValueError(f"Unable to parse sectoral title line: {blocks[0].text!r}")

    section_number = int(title_match.group("section_number"))
    section_title = title_match.group("section_title").strip()
    standard_version = title_match.group("version")

    topics: list[SectoralTopic] = []
    topics_by_code: dict[str, SectoralTopic] = {}
    current_topic: SectoralTopic | None = None

    for idx, block in enumerate(blocks[1:], start=1):
        topic_match = is_topic_paragraph(block)
        if topic_match:
            next_block = next_nonempty_block(blocks, idx)
            if next_block is not None and is_topic_paragraph(next_block):
                continue
            topic_code = topic_match.group("topic_code")
            current_topic = topics_by_code.get(topic_code)
            if current_topic is None:
                current_topic = SectoralTopic(
                    topic_code=topic_code,
                    title=topic_match.group("title").strip(),
                    sort_order=int(topic_code.split(".")[1]),
                )
                topics.append(current_topic)
                topics_by_code[topic_code] = current_topic
            continue

        if isinstance(block, TableBlock) and current_topic is not None and is_reporting_table(block):
            current_topic.entries.extend(parse_topic_entries([block]))

    if not topics:
        raise ValueError(f"No sectoral topics parsed from {path}")

    return SectoralDocument(
        standard_code=f"GRI {section_number}",
        standard_name=f"GRI {section_number}: {section_title}",
        standard_version=standard_version,
        topics=topics,
    )


async def upsert_section(
    session: AsyncSession,
    *,
    standard_id: int,
    code: str,
    title: str,
    sort_order: int,
    parent_section_id: int | None,
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
            parent_section_id=parent_section_id,
            code=code,
            title=title,
            sort_order=sort_order,
        )
        session.add(section)
        await session.flush()
        stats.created_sections += 1
        return section

    changed = False
    updates = {
        "parent_section_id": parent_section_id,
        "title": title,
        "sort_order": sort_order,
    }
    for field_name, value in updates.items():
        if getattr(section, field_name) != value:
            setattr(section, field_name, value)
            changed = True
    if changed:
        await session.flush()
        stats.updated_sections += 1
    return section


async def import_sectoral_docx(
    session: AsyncSession,
    parsed: SectoralDocument,
    *,
    with_shared_elements: bool,
) -> ImportStats:
    stats = ImportStats()
    standard_stub = SimpleNamespace(
        standard_code=parsed.standard_code,
        standard_name=parsed.standard_name,
        standard_version=parsed.standard_version,
    )
    standard = await get_or_create_standard(session, standard_stub)

    for topic in parsed.topics:
        topic_section = await upsert_section(
            session,
            standard_id=standard.id,
            code=f"GRI {topic.topic_code}",
            title=topic.title,
            sort_order=topic.sort_order,
            parent_section_id=None,
            stats=stats,
        )

        subgroup_sections: dict[str, StandardSection] = {}
        for group_key in GROUP_TITLES:
            if any(entry.group_key == group_key for entry in topic.entries):
                subgroup_sections[group_key] = await upsert_section(
                    session,
                    standard_id=standard.id,
                    code=f"GRI {topic.topic_code}.{GROUP_SUFFIXES[group_key]}",
                    title=GROUP_TITLES[group_key],
                    sort_order=GROUP_SORT_ORDERS[group_key],
                    parent_section_id=topic_section.id,
                    stats=stats,
                )

        concept_domain = re.sub(r"[^a-z0-9]+", "_", topic.title.lower()).strip("_")

        for entry in topic.entries:
            disclosure = parse_entry(
                entry,
                topic_code=topic.topic_code,
                topic_title=topic.title,
            )
            section_id = subgroup_sections[entry.group_key].id
            disclosure_row = await upsert_disclosure(
                session,
                standard.id,
                section_id,
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


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import a GRI sectoral DOCX into the framework catalog.")
    parser.add_argument(
        "docx_path",
        type=Path,
        help="Path to a sectoral GRI DOCX document or a directory of DOCX documents.",
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


async def run_single_import(
    session_factory: async_sessionmaker[AsyncSession],
    path: Path,
    *,
    apply: bool,
    with_shared_elements: bool,
) -> DocumentRunResult:
    parsed = parse_docx(path)
    disclosure_count = sum(len(topic.entries) for topic in parsed.topics)
    item_count = sum(
        len(
            parse_entry(
                entry,
                topic_code=topic.topic_code,
                topic_title=topic.title,
            ).datapoints
        )
        for topic in parsed.topics
        for entry in topic.entries
    )

    async with session_factory() as session:
        stats = await import_sectoral_docx(
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
        disclosure_count=disclosure_count,
        item_count=item_count,
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
            print(f"  Standard:    {result.parsed.standard_code} - {result.parsed.standard_name}")
            print(f"  Version:     {result.parsed.standard_version}")
            print(f"  Topics:      {len(result.parsed.topics)}")
            print(f"  Disclosures: {result.disclosure_count}")
            print(f"  DataPoints:  {result.item_count}")
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
