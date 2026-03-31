from __future__ import annotations

import argparse
import asyncio
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
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

PDF_TITLE_RE = re.compile(r"^GRI\s+2:\s+General Disclosures\s+2021$")
DISCLOSURE_RE = re.compile(r"^Disclosure\s+(?P<raw_code>2-\d+)\s+(?P<title>.+)$")
MARKER_RE = re.compile(r"^(?P<marker>REQUIREMENTS?|GUIDANCE)\s*(?P<remainder>.*)$")
LETTER_CLAUSE_RE = re.compile(r"^(?P<label>[a-z])\.\s+(?P<text>.+)$")
ROMAN_CLAUSE_RE = re.compile(
    r"^(?P<label>i|ii|iii|iv|v|vi|vii|viii|ix|x)\.\s+(?P<text>.+)$"
)
TABLE_TITLE_RE = re.compile(r"^Table\s+\d+\.\s+.+$")
PAGE_HEADER_RE = re.compile(r"^\d+\s+GRI 2: General Disclosures 2021$")
NUMERIC_CITATION_RE = re.compile(r"\[(\d+)\]")
REFERENCE_NOISE_PATTERNS = (
    re.compile(r"^See references? \[[^\]]+\].*Bibliography\.?$", re.IGNORECASE),
    re.compile(r"^See the Bibliography\b.*$", re.IGNORECASE),
    re.compile(r"^See Table \d+.*$", re.IGNORECASE),
    re.compile(r"^.*see reference \[\d+\] in the Bibliography\.?$", re.IGNORECASE),
    re.compile(r"^reference \[\d+\] in the Bibliography\b.*$", re.IGNORECASE),
)


@dataclass
class RequirementClause:
    label: str
    code: str
    text: str
    children: list["RequirementClause"] = field(default_factory=list)


@dataclass
class GuidanceSection:
    heading: str | None
    chunks: list[str] = field(default_factory=list)


@dataclass
class PdfRunResult:
    path: Path
    parsed: ParsedDocument
    total_items: int
    stats: ImportStats


def extract_pdf_lines(path: Path) -> list[str]:
    result = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.replace("\f", "\n").splitlines()


def normalize_text(text: str) -> str:
    return " ".join(text.split()).strip()


def strip_numeric_citations(text: str) -> str:
    return normalize_text(NUMERIC_CITATION_RE.sub("", text))


def is_page_noise(text: str) -> bool:
    return (
        not text
        or text == "GRI 2: General Disclosures 2021"
        or text == "UNIVERSAL STANDARD 2"
        or PAGE_HEADER_RE.match(text) is not None
    )


def is_reference_noise(text: str) -> bool:
    return any(pattern.match(text) for pattern in REFERENCE_NOISE_PATTERNS)


def find_marker_index(lines: list[str], marker: str, start: int, end: int) -> int | None:
    marker_upper = marker.upper()
    for idx in range(start, end):
        stripped = lines[idx].strip()
        match = MARKER_RE.match(stripped)
        if match and match.group("marker").upper().startswith(marker_upper):
            return idx
    return None


def marker_remainder(line: str, marker: str) -> str:
    stripped = line.strip()
    match = MARKER_RE.match(stripped)
    if not match:
        return ""
    if not match.group("marker").upper().startswith(marker.upper()):
        return ""
    return normalize_text(match.group("remainder"))


def find_actual_disclosure_indices(lines: list[str]) -> list[int]:
    candidates = [idx for idx, line in enumerate(lines) if DISCLOSURE_RE.match(line.strip())]
    actual: list[int] = []
    for pos, idx in enumerate(candidates):
        next_idx = candidates[pos + 1] if pos + 1 < len(candidates) else len(lines)
        window_end = min(next_idx, idx + 70)
        if any(
            (match := MARKER_RE.match(lines[cursor].strip()))
            and match.group("marker").upper().startswith("REQUIREMENT")
            for cursor in range(idx + 1, window_end)
        ):
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
        if stripped == "The organization shall:":
            preface = stripped
            break
        if MARKER_RE.match(stripped):
            break
        if stripped:
            title_parts.append(stripped)

    return raw_code, " ".join(title_parts).strip(), preface


def parse_requirement_clauses(
    requirement_lines: list[str],
    *,
    raw_code: str,
) -> tuple[list[str], list[RequirementClause]]:
    preface_lines: list[str] = []
    clauses: list[RequirementClause] = []
    current_top: RequirementClause | None = None
    current_child: RequirementClause | None = None

    for raw_line in requirement_lines:
        stripped = strip_numeric_citations(raw_line.strip())
        if is_page_noise(stripped):
            continue
        if not stripped:
            continue

        letter_match = LETTER_CLAUSE_RE.match(stripped)
        roman_match = ROMAN_CLAUSE_RE.match(stripped)

        if roman_match and current_top is not None:
            label = roman_match.group("label")
            current_child = RequirementClause(
                label=label,
                code=f"{current_top.code}-{label}",
                text=normalize_text(roman_match.group("text")),
            )
            current_top.children.append(current_child)
            continue

        if letter_match:
            label = letter_match.group("label")
            current_top = RequirementClause(
                label=label,
                code=f"{raw_code}-{label}",
                text=normalize_text(letter_match.group("text")),
            )
            clauses.append(current_top)
            current_child = None
            continue

        target = current_child or current_top
        if target is None:
            preface_lines.append(stripped)
        else:
            target.text = normalize_text(f"{target.text} {stripped}")

    return preface_lines, clauses


def combine_clause_text(parent_text: str, child_text: str) -> str:
    parent = parent_text.rstrip(":; ")
    child = child_text.lstrip()
    if not parent:
        return child
    return normalize_text(f"{parent} {child}")


def clause_leaves(clause: RequirementClause) -> list[tuple[str, str]]:
    if not clause.children:
        return [(clause.code, clause.text)]

    leaves: list[tuple[str, str]] = []
    for child in clause.children:
        leaves.extend(
            (child.code, combine_clause_text(clause.text, leaf_text))
            for _leaf_code, leaf_text in clause_leaves(child)
        )
    return leaves


def strip_clause_terminator(text: str) -> str:
    return text.rstrip(" ;.")


def split_series_items(text: str) -> list[str]:
    normalized = strip_clause_terminator(normalize_text(text))
    lowered = f" {normalized.lower()} "
    complex_markers = (
        " that ",
        " which ",
        " who ",
        " if ",
        " whether ",
        " how ",
        " why ",
        " where ",
        " when ",
        " including ",
        ":",
    )
    verb_markers = (
        " is ",
        " are ",
        " was ",
        " were ",
        " be ",
        " been ",
        " being ",
        " can ",
        " could ",
        " should ",
        " may ",
        " might ",
        " will ",
        " would ",
        " has ",
        " have ",
        " had ",
    )
    if any(marker in lowered for marker in complex_markers):
        return [normalized]

    if "," in normalized:
        candidate = normalized.replace(", and ", ", ")
        tokens = [normalize_text(token) for token in candidate.split(",") if token.strip()]
        if len(tokens) > 1:
            return tokens

    if " and " in normalized and not any(marker in lowered for marker in verb_markers):
        tokens = [normalize_text(token) for token in normalized.split(" and ") if token.strip()]
        if len(tokens) > 1:
            return tokens

    return [normalized]


def split_including_details(details: str) -> list[str]:
    normalized = strip_clause_terminator(normalize_text(details))
    lowered = normalized.lower()

    if lowered.startswith("whether and how "):
        remainder = normalized[len("whether and how ") :].strip()
        return [f"whether {remainder}", f"how {remainder}"]

    if ", and how " in lowered:
        split_match = re.search(r",\s+and\s+(how .+)$", normalized, flags=re.IGNORECASE)
        if not split_match:
            return [normalized]
        first = normalize_text(normalized[: split_match.start()])
        second = normalize_text(split_match.group(1))
        if second.lower().startswith("how they "):
            second = f"how {first} {second[len('how they '):].strip()}"
        return [first, second]

    if ", and the frequency of " in lowered:
        split_match = re.search(
            r",\s+and\s+(the frequency of .+)$",
            normalized,
            flags=re.IGNORECASE,
        )
        if not split_match:
            return [normalized]
        first = normalize_text(normalized[: split_match.start()])
        second = normalize_text(split_match.group(1))
        return [first, second]

    return split_series_items(normalized)


def split_reporting_period_and_frequency(text: str) -> list[str] | None:
    match = re.match(
        r"^(?P<verb>specify|report|describe)\s+the reporting period for,\s+and the frequency of,\s+(?P<subject>.+)$",
        strip_clause_terminator(text),
        re.IGNORECASE,
    )
    if not match:
        return None

    verb = match.group("verb").lower()
    subject = normalize_text(match.group("subject"))
    return [
        f"{verb} the reporting period for {subject}",
        f"{verb} the frequency of {subject}",
    ]


def split_or_if_explain(text: str) -> list[str] | None:
    match = re.match(
        r"^(?P<verb>provide|report|describe|specify)\s+(?P<main>.+?),\s+or,?\s+if\s+(?P<condition>.+?),\s+explain\s+(?P<reason>.+)$",
        strip_clause_terminator(text),
        re.IGNORECASE,
    )
    if not match:
        return None

    verb = match.group("verb").lower()
    main = normalize_text(match.group("main"))
    condition = normalize_text(match.group("condition"))
    reason = normalize_text(match.group("reason"))
    return [
        f"{verb} {main}",
        f"explain {reason} if {condition}",
    ]


def split_breakdown_clause(text: str) -> list[str] | None:
    match = re.match(
        r"^(?P<verb>report|describe|list|provide|specify)\s+(?P<subject>.+?),\s+and\s+(?P<breakdown>a breakdown(?: of (?:this|the) total)?)\s+by\s+(?P<dimensions>.+)$",
        strip_clause_terminator(text),
        re.IGNORECASE,
    )
    if not match:
        return None

    verb = match.group("verb").lower()
    subject = normalize_text(match.group("subject"))
    dimensions = normalize_text(match.group("dimensions"))
    dimension_items = [
        normalize_text(item)
        for item in re.split(r"\s+and\s+by\s+", dimensions)
        if item.strip()
    ]
    if not dimension_items:
        dimension_items = [dimensions]

    subject_target = subject
    if subject.lower().startswith("the total number of "):
        subject_target = normalize_text(subject[len("the total number of ") :])

    return [
        f"{verb} {subject}",
        *[f"{verb} a breakdown of {subject_target} by {dimension}" for dimension in dimension_items],
    ]


def split_total_number_and_monetary_value(text: str) -> list[str] | None:
    match = re.match(
        r"^report\s+the total number and the monetary value of\s+(?P<subject>.+)$",
        strip_clause_terminator(text),
        re.IGNORECASE,
    )
    if not match:
        return None

    subject = normalize_text(match.group("subject"))
    return [
        f"report the total number of {subject}",
        f"report the monetary value of {subject}",
    ]


def split_tail_clause(text: str) -> list[str] | None:
    match = re.match(
        r"^(?P<first>(?:if .+?,\s+)?(?:report|describe|list|provide|specify|explain)\s+.+?),\s+and\s+(?P<tail>report .+|describe .+|explain .+|how .+|the frequency of .+|the nature of .+|the purpose of .+|the reasons? .+)$",
        strip_clause_terminator(text),
        re.IGNORECASE,
    )
    if not match:
        return None

    first = normalize_text(match.group("first"))
    tail = normalize_text(match.group("tail"))
    if tail.lower().startswith(("report ", "describe ", "explain ")):
        second = tail
    elif first.lower().startswith("if "):
        condition, _, action = first.partition(", ")
        verb = action.split(" ", 1)[0].lower()
        second = f"{condition}, {verb} {tail}"
    else:
        verb = first.split(" ", 1)[0].lower()
        second = f"{verb} {tail}"
    return [first, second]


def split_conditional_explain_series(text: str) -> list[str] | None:
    match = re.match(
        r"^(?P<prefix>if .+?(?:,\s+|\s+))?explain\s+(?P<body>.+)$",
        strip_clause_terminator(text),
        re.IGNORECASE,
    )
    if not match:
        return None

    body = normalize_text(match.group("body"))
    if ", and how " in body.lower():
        split_match = re.search(r",\s+and\s+(how .+)$", body, flags=re.IGNORECASE)
        if not split_match:
            return None
        first = normalize_text(body[: split_match.start()])
        second = normalize_text(split_match.group(1))
        series_items = [*split_series_items(first), second]
    else:
        series_items = split_series_items(body)
    if len(series_items) <= 1:
        return None

    prefix = normalize_text(match.group("prefix") or "")
    if prefix:
        return [f"{prefix} explain {item}" for item in series_items]
    return [f"explain {item}" for item in series_items]


def split_contextual_including_clause(text: str) -> list[str] | None:
    match = re.match(
        r"^(?P<prefix>if .+?(?:,\s+|\s+))?(?P<verb>report|describe|list|provide|specify|explain)\s+(?P<main>.+?),\s+including\s+(?P<details>.+)$",
        strip_clause_terminator(text),
        re.IGNORECASE,
    )
    if not match:
        return None

    detail_items = split_including_details(match.group("details"))
    if len(detail_items) <= 1:
        return None

    prefix = normalize_text(match.group("prefix") or "")
    verb = match.group("verb").lower()
    main = normalize_text(match.group("main"))
    prefix_part = f"{prefix} " if prefix else ""
    return [
        f"{prefix_part}{verb} {main}, including {detail}"
        for detail in detail_items
    ]


def expand_leaf_clause(clause_code: str, clause_text: str) -> list[tuple[str, str]]:
    candidates = [(clause_code, strip_clause_terminator(clause_text))]
    splitters = (
        split_reporting_period_and_frequency,
        split_or_if_explain,
        split_breakdown_clause,
        split_total_number_and_monetary_value,
        split_conditional_explain_series,
        split_contextual_including_clause,
        split_tail_clause,
    )

    expanded = True
    while expanded:
        expanded = False
        next_candidates: list[tuple[str, str]] = []
        for code, text in candidates:
            split_result: list[str] | None = None
            for splitter in splitters:
                split_result = splitter(text)
                if split_result and len(split_result) > 1:
                    next_candidates.extend(
                        (f"{code}.{idx}", strip_clause_terminator(part))
                        for idx, part in enumerate(split_result, start=1)
                    )
                    expanded = True
                    break
            else:
                next_candidates.append((code, strip_clause_terminator(text)))
        candidates = next_candidates

    deduped: list[tuple[str, str]] = []
    seen_labels: set[str] = set()
    for code, text in candidates:
        normalized_text = strip_clause_terminator(normalize_text(text))
        if normalized_text in seen_labels:
            continue
        seen_labels.add(normalized_text)
        deduped.append((code, normalized_text))

    return deduped


def clauses_to_markdown(clauses: list[RequirementClause], indent: int = 0) -> list[str]:
    lines: list[str] = []
    prefix = "  " * indent
    for clause in clauses:
        lines.append(f"{prefix}- {clause.code} {clause.text}")
        if clause.children:
            lines.extend(clauses_to_markdown(clause.children, indent + 1))
    return lines


def serialize_clause(clause: RequirementClause) -> dict:
    return {
        "label": clause.label,
        "code": clause.code,
        "text": clause.text,
        "children": [serialize_clause(child) for child in clause.children],
    }


def consume_table(lines: list[str], start: int, end: int) -> tuple[str, int]:
    title = strip_numeric_citations(lines[start].strip())
    collected: list[str] = []
    idx = start + 1

    while idx < end:
        stripped = lines[idx].strip()
        if is_page_noise(stripped):
            idx += 1
            continue
        if TABLE_TITLE_RE.match(stripped) or DISCLOSURE_RE.match(stripped) or stripped.startswith("Guidance to "):
            break
        if MARKER_RE.match(stripped):
            break
        if not stripped:
            idx += 1
            continue
        collected.append(stripped)
        idx += 1

    placeholders: list[str] = []
    columns: list[str] = []
    rows: list[str] = []
    notes: list[str] = []

    for entry in collected:
        raw_without_citations = NUMERIC_CITATION_RE.sub("", entry).strip()
        cleaned = normalize_text(raw_without_citations)
        if not cleaned:
            continue
        if cleaned.startswith("*"):
            notes.append(cleaned.lstrip("*").strip())
            continue

        split_columns = [
            normalize_text(token)
            for token in re.split(r"\s{2,}", raw_without_citations)
            if token.strip()
        ]
        if cleaned.startswith("[") and cleaned.endswith("]"):
            placeholders.append(cleaned)
            continue

        if len(split_columns) > 1 and not columns:
            columns = split_columns
            continue

        rows.append(cleaned)

    markdown_lines = [title]
    if placeholders:
        markdown_lines.append("- Placeholders:")
        for placeholder in placeholders:
            markdown_lines.append(f"  - {placeholder}")
    if columns:
        markdown_lines.append("- Columns:")
        for column in columns:
            markdown_lines.append(f"  - {column}")
    if rows:
        markdown_lines.append("- Rows:")
        for row in rows:
            markdown_lines.append(f"  - {row}")
    for note in notes:
        markdown_lines.append(f"- Note: {note}")

    return "\n".join(markdown_lines).strip(), idx


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
        stripped = guidance_lines[idx].strip()
        if is_page_noise(stripped):
            flush_paragraph()
            idx += 1
            continue
        if not stripped:
            flush_paragraph()
            idx += 1
            continue
        if is_reference_noise(stripped):
            flush_paragraph()
            idx += 1
            continue
        if TABLE_TITLE_RE.match(stripped):
            flush_paragraph()
            table_markdown, idx = consume_table(guidance_lines, idx, len(guidance_lines))
            current.chunks.append(table_markdown)
            continue

        cleaned = strip_numeric_citations(stripped)
        if not cleaned:
            idx += 1
            continue

        if cleaned.startswith("Guidance to "):
            flush_paragraph()
            if current.heading or current.chunks:
                sections.append(current)
            current = GuidanceSection(heading=cleaned, chunks=[])
            idx += 1
            continue

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
        parts.extend(section.chunks)
    return "\n\n".join(part for part in parts if part).strip()


def build_disclosure_description(blocks: list[dict]) -> str:
    sections: list[str] = []
    for block in blocks:
        body = (block.get("body_md") or "").strip()
        if not body:
            continue
        sections.append(f'{block["title"]}\n{body}')
    return "\n\n".join(sections).strip()


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
    leaf_clauses = [
        expanded_leaf
        for clause in clauses
        for clause_code, clause_text in clause_leaves(clause)
        for expanded_leaf in expand_leaf_clause(clause_code, clause_text)
    ]

    datapoints: list[ParsedDataPoint] = []
    for clause_code, clause_text in leaf_clauses:
        item_type, value_type, unit_code = infer_item_shape(clause_text)
        datapoints.append(
            ParsedDataPoint(
                raw_code=clause_code,
                item_code=f"GRI {clause_code}",
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
    requirement_markdown_parts.extend(clauses_to_markdown(clauses))
    requirements_body = "\n".join(part for part in requirement_markdown_parts if part).strip()

    guidance_body = guidance_sections_to_markdown(guidance_sections)

    content_blocks = [
        {
            "type": "requirements",
            "title": "Requirements",
            "body_md": requirements_body or None,
            "paragraphs": [],
            "items": [clause_text for _code, clause_text in leaf_clauses],
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
        "source_format": "gri_2_pdf_v1",
        "section_code": "GRI 2",
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
    if not any(PDF_TITLE_RE.match(line.strip()) for line in lines[:5]):
        raise ValueError("Unable to identify GRI 2 title in the PDF")

    disclosure_indices = find_actual_disclosure_indices(lines)
    if not disclosure_indices:
        raise ValueError("Unable to locate disclosure content in the PDF")

    disclosures = [
        parse_disclosure(
            lines,
            idx,
            disclosure_indices[pos + 1] if pos + 1 < len(disclosure_indices) else len(lines),
        )
        for pos, idx in enumerate(disclosure_indices)
    ]

    if len(disclosures) != 30:
        raise ValueError(f"Expected 30 disclosures for GRI 2, parsed {len(disclosures)}")

    return ParsedDocument(
        standard_code="GRI",
        standard_name="GRI Standards",
        standard_version="2021",
        section_code="GRI 2",
        section_title="General Disclosures",
        section_sort_order=2,
        disclosures=disclosures,
    )


async def import_gri_2_pdf(
    session: AsyncSession,
    parsed: ParsedDocument,
    *,
    with_shared_elements: bool,
) -> ImportStats:
    stats = ImportStats()
    standard = await get_or_create_standard(session, parsed)
    section = await upsert_section(session, standard.id, parsed, stats)
    concept_domain = "general_disclosures"

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
            stats = await import_gri_2_pdf(
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
    parser = argparse.ArgumentParser(description="Import GRI 2 General Disclosures 2021 from PDF.")
    parser.add_argument("pdf_path", type=Path, help="Path to the GRI 2 PDF file.")
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
