from __future__ import annotations

import argparse
import asyncio
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.db.models.standard import Standard, StandardSection
from scripts.import_gri_2_pdf import (
    build_disclosure_description,
    expand_leaf_clause,
    extract_pdf_lines,
    normalize_text,
    strip_numeric_citations,
)
from scripts.import_gri_docx import (
    ImportStats,
    ParsedDataPoint,
    ParsedDisclosure,
    deactivate_stale_requirement_items,
    ensure_mapping,
    infer_disclosure_type,
    infer_item_shape,
    upsert_disclosure,
    upsert_requirement_item,
    upsert_shared_element,
)

VERSION_RE = re.compile(r"^INDUSTRY STANDARD \| VERSION (?P<version>\d{4}-\d{2})$")
INDUSTRY_CODE_RE = re.compile(
    r"^Sustainable Industry Classification System\S* \(SICS\S*\)\s+(?P<industry_code>[A-Z]{2}-[A-Z]{2})$"
)
TOPIC_HEADER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9 &,/'().\-]+$")
METRIC_RE = re.compile(
    r"^(?P<code>[A-Z]{2}-[A-Z]{2}-\d{3}[a-z]\.\d+)\.\s*(?P<title>.*)$"
)
NOTE_RE = re.compile(r"^Note to (?P<code>[A-Z]{2}-[A-Z]{2}-\d{3}[a-z]\.\d+)$")
ACTIVITY_CODE_RE = re.compile(r"(?P<code>[A-Z]{2}-[A-Z]{2}-000\.[A-Z])$")
ACTIVITY_NOTE_RE = re.compile(
    r"^(?P<idx>\d+)\s+Note to (?P<code>[A-Z]{2}-[A-Z]{2}-000\.[A-Z])\s+[–-]\s*(?P<text>.+)$"
)
ACTIVITY_TABLE_RE = re.compile(r"^Table\s+\d+\.\s+Activity Metrics$", re.IGNORECASE)
CLAUSE_RE = re.compile(r"^(?P<label>\d+(?:\.\d+)*)\s+(?P<text>.+)$")
TABLE_TITLE_RE = re.compile(r"^Table\s+\d+\.\s+.+$")
PAGE_HEADER_RE = re.compile(
    r"^(?:\d+\s+)?SUSTAINABILITY ACCOUNTING STANDARD \| .+\| \d+$"
)
PAREN_SERIES_RE = re.compile(r"\((?P<label>\d+|[a-z])\)\s*")
MEASURE_HEAD_RE = re.compile(
    r"^(number|amount|percentage|value|volume|weight|rate|median|average)$",
    re.IGNORECASE,
)
TOPIC_SECTION_STOPWORDS = {"and", "of", "the"}
ALLOWED_NOTE_VERBS = {"describe", "discuss", "provide", "disclose", "report", "list", "identify", "explain"}
DISALLOWED_NOTE_VERBS = {
    "calculate",
    "exclude",
    "include",
    "use",
    "derive",
    "multiply",
    "divide",
    "allocate",
    "estimate",
    "express",
    "adjust",
    "convert",
}


@dataclass
class NumberedClause:
    label: str
    text: str
    children: list["NumberedClause"] = field(default_factory=list)


@dataclass
class SasbParsedDisclosure:
    section_code: str
    section_title: str
    section_sort_order: int
    concept_domain: str
    disclosure: ParsedDisclosure


@dataclass
class SasbParsedStandard:
    standard_code: str
    standard_name: str
    standard_version: str
    jurisdiction: str
    disclosures: list[SasbParsedDisclosure]


@dataclass
class SasbImportResult:
    path: Path
    parsed: SasbParsedStandard
    total_items: int
    stats: ImportStats


@dataclass
class SasbBatchEntry:
    path: Path
    standard_code: str
    standard_name: str
    status: str
    message: str | None = None
    disclosures: int = 0
    datapoints: int = 0
    stats: ImportStats | None = None


def is_page_noise(text: str) -> bool:
    return (
        not text
        or text in {
            "SUSTAINABILITY DISCLOSURE TOPICS & METRICS",
            "Metrics",
            "...continued",
            "continued...",
            "sasb.org/contact",
            "| | 18",
        }
        or PAGE_HEADER_RE.match(text) is not None
    )


def next_nonempty_index(lines: list[str], start: int, end: int) -> int | None:
    for idx in range(start, end):
        if lines[idx].strip():
            return idx
    return None


def lines_to_paragraphs(lines: list[str]) -> list[str]:
    paragraphs: list[str] = []
    current: list[str] = []
    for raw_line in lines:
        stripped = strip_numeric_citations(raw_line.strip())
        if is_page_noise(stripped):
            continue
        if not stripped:
            if current:
                paragraphs.append(normalize_text(" ".join(current)))
                current = []
            continue
        current.append(stripped)
    if current:
        paragraphs.append(normalize_text(" ".join(current)))
    return paragraphs


def strip_trailing_footnote_number(text: str) -> str:
    return re.sub(r"\s+\d+$", "", normalize_text(text)).strip()


def strip_clause_terminator(text: str) -> str:
    return text.rstrip(" ;.:")


def clause_depth(label: str) -> int:
    return label.count(".") + 1


def parse_numbered_clauses(lines: list[str]) -> tuple[list[str], list[NumberedClause]]:
    preface: list[str] = []
    roots: list[NumberedClause] = []
    stack: list[NumberedClause] = []
    current: NumberedClause | None = None

    for raw_line in lines:
        stripped = strip_numeric_citations(raw_line.strip())
        if is_page_noise(stripped):
            continue
        if not stripped:
            continue

        match = CLAUSE_RE.match(stripped)
        if match:
            label = match.group("label")
            node = NumberedClause(label=label, text=normalize_text(match.group("text")))
            level = clause_depth(label)
            while len(stack) >= level:
                stack.pop()
            if stack:
                stack[-1].children.append(node)
            else:
                roots.append(node)
            stack.append(node)
            current = node
            continue

        if current is None:
            preface.append(stripped)
        else:
            current.text = normalize_text(f"{current.text} {stripped}")

    return preface, roots


def clauses_to_markdown(clauses: list[NumberedClause], indent: int = 0) -> list[str]:
    lines: list[str] = []
    prefix = "  " * indent
    for clause in clauses:
        lines.append(f"{prefix}- {clause.label} {clause.text}")
        if clause.children:
            lines.extend(clauses_to_markdown(clause.children, indent + 1))
    return lines


def serialize_clause(clause: NumberedClause) -> dict:
    return {
        "label": clause.label,
        "text": clause.text,
        "children": [serialize_clause(child) for child in clause.children],
    }


def combine_clause_text(parent_text: str, child_text: str) -> str:
    parent = parent_text.rstrip(":; ")
    child = child_text.lstrip()
    if not parent:
        return child
    return normalize_text(f"{parent} {child}")


def clause_leaves(clause: NumberedClause) -> list[tuple[str, str]]:
    if not clause.children:
        return [(clause.label, clause.text)]

    leaves: list[tuple[str, str]] = []
    for child in clause.children:
        leaves.extend(
            (child.label, combine_clause_text(clause.text, leaf_text))
            for _leaf_label, leaf_text in clause_leaves(child)
        )
    return leaves


def topic_section_code(industry_code: str, title: str, used_codes: set[str]) -> str:
    words = [
        token
        for token in re.findall(r"[A-Za-z0-9]+", title)
        if token.lower() not in TOPIC_SECTION_STOPWORDS
    ]
    initials = "".join(word[0].upper() for word in words)[:6] or "TOPIC"
    code = f"{industry_code}-{initials}"
    if code not in used_codes:
        used_codes.add(code)
        return code

    slug = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-").upper()[:24] or "TOPIC"
    code = f"{industry_code}-{slug}"
    if code not in used_codes:
        used_codes.add(code)
        return code

    counter = 2
    while f"{code}-{counter}" in used_codes:
        counter += 1
    final_code = f"{code}-{counter}"
    used_codes.add(final_code)
    return final_code


def concept_domain_from_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_") or "general"


def consume_matrix_table(lines: list[str], start: int, end: int) -> tuple[dict, int]:
    title = strip_numeric_citations(lines[start].strip())
    idx = start + 1
    raw_lines: list[str] = []
    while idx < end:
        stripped = lines[idx].rstrip()
        compact = stripped.strip()
        if not compact:
            raw_lines.append("")
            idx += 1
            continue
        if is_page_noise(compact):
            idx += 1
            continue
        if compact.startswith("Note to ") or TABLE_TITLE_RE.match(compact):
            break
        raw_lines.append(stripped)
        idx += 1

    columns: list[str] = []
    rows: list[str] = []
    notes: list[str] = []
    row_parts: list[str] = []

    for raw_line in raw_lines:
        compact = raw_line.strip()
        if not compact:
            if row_parts:
                rows.append(normalize_text(" ".join(row_parts)))
                row_parts = []
            continue
        if compact.startswith("*"):
            if row_parts:
                rows.append(normalize_text(" ".join(row_parts)))
                row_parts = []
            notes.append(compact.lstrip("*").strip())
            continue
        if not columns:
            tokens = [normalize_text(token) for token in re.split(r"\s{2,}", compact) if token.strip()]
            if len(tokens) > 1:
                columns = tokens
                continue
        row_parts.append(compact)

    if row_parts:
        rows.append(normalize_text(" ".join(row_parts)))

    markdown_lines = [title]
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

    return {
        "type": "table",
        "title": title,
        "body_md": "\n".join(markdown_lines),
        "paragraphs": [],
        "items": [],
        "metadata": {
            "columns": columns,
            "rows": rows,
            "notes": notes,
        },
    }, idx


def parse_standard_metadata(lines: list[str]) -> tuple[str, str, str]:
    title_parts: list[str] = []
    cursor = 0
    while cursor < len(lines):
        stripped = lines[cursor].strip()
        if not stripped:
            cursor += 1
            continue
        if stripped == "Sustainability Accounting Standard":
            break
        title_parts.append(stripped)
        cursor += 1

    standard_name = normalize_text(" ".join(title_parts))
    industry_code = ""
    version = ""
    for line in lines[:80]:
        stripped = line.strip()
        if not stripped:
            continue
        if not industry_code:
            match = INDUSTRY_CODE_RE.match(stripped)
            if match:
                industry_code = match.group("industry_code")
                continue
        if not version:
            match = VERSION_RE.match(stripped)
            if match:
                version = match.group("version")
                continue
        if industry_code and version:
            break

    if not standard_name or not industry_code or not version:
        raise ValueError("Unable to parse SASB standard metadata from PDF")
    return standard_name, industry_code, version


def resolve_standard_identity(
    industry_name: str,
    industry_code: str,
    *,
    standard_code: str | None,
    standard_name: str | None,
) -> tuple[str, str]:
    return (
        standard_code or f"SASB-{industry_code}",
        standard_name or f"SASB {industry_name}",
    )


def peek_sasb_identity(path: Path, *, standard_code: str | None, standard_name: str | None) -> tuple[str, str, str]:
    lines = extract_pdf_lines(path)
    industry_name, industry_code, _version = parse_standard_metadata(lines)
    return resolve_standard_identity(
        industry_name,
        industry_code,
        standard_code=standard_code,
        standard_name=standard_name,
    )


def find_topic_ranges(lines: list[str]) -> list[tuple[str, int, int]]:
    starts: list[tuple[str, int]] = []
    for idx, raw_line in enumerate(lines):
        stripped = raw_line.strip()
        if not stripped or is_page_noise(stripped):
            continue
        if not TOPIC_HEADER_RE.match(stripped):
            continue
        next_idx = next_nonempty_index(lines, idx + 1, min(len(lines), idx + 8))
        if next_idx is None:
            continue
        if lines[next_idx].strip() == "Topic Summary":
            starts.append((stripped, idx))

    ranges: list[tuple[str, int, int]] = []
    for pos, (title, start_idx) in enumerate(starts):
        end_idx = starts[pos + 1][1] if pos + 1 < len(starts) else len(lines)
        ranges.append((title, start_idx, end_idx))
    return ranges


def parse_metric_body(
    lines: list[str],
    start: int,
    end: int,
) -> tuple[str, list[str], list[dict], list[str]]:
    match = METRIC_RE.match(lines[start].strip())
    if not match:
        raise ValueError(f"Unable to parse SASB metric heading: {lines[start]!r}")

    title_parts = [normalize_text(match.group("title"))] if match.group("title") else []
    idx = start + 1
    while idx < end:
        stripped = lines[idx].strip()
        if is_page_noise(stripped):
            idx += 1
            continue
        if not stripped:
            idx += 1
            continue
        if CLAUSE_RE.match(stripped) or TABLE_TITLE_RE.match(stripped) or NOTE_RE.match(stripped):
            break
        title_parts.append(normalize_text(stripped))
        idx += 1

    clause_lines: list[str] = []
    table_blocks: list[dict] = []
    note_lines: list[str] = []

    while idx < end:
        stripped = lines[idx].strip()
        if is_page_noise(stripped):
            idx += 1
            continue
        if NOTE_RE.match(stripped):
            note_lines.extend(lines[idx + 1 : end])
            break
        if TABLE_TITLE_RE.match(stripped):
            table_block, idx = consume_matrix_table(lines, idx, end)
            table_blocks.append(table_block)
            continue
        clause_lines.append(lines[idx])
        idx += 1

    return " ".join(part for part in title_parts if part).strip(), clause_lines, table_blocks, note_lines


def parse_topic_metrics(
    lines: list[str],
    topic_title: str,
    topic_start: int,
    topic_end: int,
) -> list[tuple[str, str, list[str], list[dict], list[str], int]]:
    metrics_idx = next(
        (idx for idx in range(topic_start, topic_end) if lines[idx].strip() == "Metrics"),
        None,
    )
    if metrics_idx is None:
        raise ValueError(f"Unable to locate Metrics block for topic {topic_title!r}")

    metric_starts = [
        idx for idx in range(metrics_idx + 1, topic_end) if METRIC_RE.match(lines[idx].strip())
    ]
    parsed: list[tuple[str, str, list[str], list[dict], list[str], int]] = []
    for pos, start_idx in enumerate(metric_starts):
        end_idx = metric_starts[pos + 1] if pos + 1 < len(metric_starts) else topic_end
        match = METRIC_RE.match(lines[start_idx].strip())
        assert match is not None
        code = match.group("code")
        title, clause_lines, table_blocks, note_lines = parse_metric_body(lines, start_idx, end_idx)
        parsed.append((code, title, clause_lines, table_blocks, note_lines, pos + 1))
    return parsed


def parse_topic_summary(lines: list[str], start: int, end: int) -> str:
    summary_idx = next(
        (idx for idx in range(start, end) if lines[idx].strip() == "Topic Summary"),
        None,
    )
    metrics_idx = next(
        (idx for idx in range(start, end) if lines[idx].strip() == "Metrics"),
        None,
    )
    if summary_idx is None or metrics_idx is None or summary_idx >= metrics_idx:
        return ""
    return "\n\n".join(lines_to_paragraphs(lines[summary_idx + 1 : metrics_idx])).strip()


def parse_activity_metrics(
    lines: list[str],
) -> list[tuple[str, str, str | None, int]]:
    table_start = next(
        (idx for idx, line in enumerate(lines) if ACTIVITY_TABLE_RE.match(line.strip())),
        None,
    )
    if table_start is None:
        return []

    topic_ranges = find_topic_ranges(lines)
    if not topic_ranges:
        return []
    activity_end = topic_ranges[0][1]
    activity_lines = lines[table_start + 1 : activity_end]

    note_by_code: dict[str, str] = {}
    table_lines: list[str] = []
    current_code: str | None = None
    current_parts: list[str] = []
    idx = 0
    while idx < len(activity_lines):
        stripped = activity_lines[idx].strip()
        if is_page_noise(stripped):
            table_lines.append(activity_lines[idx])
            idx += 1
            continue

        match = ACTIVITY_NOTE_RE.match(stripped)
        if match:
            if current_code is not None and current_parts:
                note_by_code[current_code] = normalize_text(" ".join(current_parts))
            current_code = match.group("code")
            current_parts = [strip_numeric_citations(match.group("text"))]
            idx += 1
            while idx < len(activity_lines):
                continuation = activity_lines[idx].strip()
                if (
                    not continuation
                    or is_page_noise(continuation)
                    or ACTIVITY_NOTE_RE.match(continuation)
                    or ACTIVITY_CODE_RE.search(continuation)
                    or "ACTIVITY METRIC" in continuation
                ):
                    break
                current_parts.append(strip_numeric_citations(continuation))
                idx += 1
            continue

        if current_code is not None and current_parts:
            note_by_code[current_code] = normalize_text(" ".join(current_parts))
            current_code = None
            current_parts = []

        table_lines.append(activity_lines[idx])
        idx += 1

    if current_code is not None and current_parts:
        note_by_code[current_code] = normalize_text(" ".join(current_parts))

    parsed: list[tuple[str, str, str | None, int]] = []
    pending_prefix: list[str] = []
    idx = 0
    while idx < len(table_lines):
        stripped = table_lines[idx].rstrip()
        compact = stripped.strip()
        if (
            is_page_noise(compact)
            or "ACTIVITY METRIC" in compact
            or compact in {"CATEGORY", "CODE", "UNIT OF", "MEASURE"}
            or "Note to " in compact
        ):
            if "Note to " in compact:
                pending_prefix = []
            idx += 1
            continue
        match = ACTIVITY_CODE_RE.search(compact)
        if match:
            code = match.group("code")
            title_parts = [part for part in pending_prefix if part]
            pending_prefix = []
            tokens = [normalize_text(token) for token in re.split(r"\s{2,}", compact) if token.strip()]
            if tokens and tokens[0] not in {"Quantitative", "Discussion and", "Analysis"}:
                if code in tokens:
                    tokens = [token for token in tokens if token != code]
                if tokens and tokens[0] not in {"Quantitative", "Number", "Discussion and Analysis", "n/a"}:
                    title_parts.append(tokens[0])
            idx += 1
            while idx < len(table_lines):
                next_compact = table_lines[idx].strip()
                if (
                    not next_compact
                    or is_page_noise(next_compact)
                    or ACTIVITY_CODE_RE.search(next_compact)
                    or next_compact == "continued..."
                    or "ACTIVITY METRIC" in next_compact
                ):
                    break
                title_parts.append(next_compact)
                idx += 1
            title = strip_trailing_footnote_number(" ".join(title_parts))
            parsed.append((code, title, note_by_code.get(code), len(parsed) + 1))
            continue

        if (
            compact not in {"continued...", "UNIT OF", "MEASURE", "CATEGORY"}
            and "ACTIVITY METRIC" not in compact
            and "CODE" not in compact
            and compact[:1].isupper()
        ):
            pending_prefix.append(compact)
        idx += 1

    return parsed


def clean_series_fragment(text: str) -> str:
    cleaned = strip_clause_terminator(strip_trailing_footnote_number(strip_numeric_citations(text)))
    cleaned = re.sub(r"^(?:and|or)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(?:and|or)$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip(" ,;:")


def split_parenthetical_series(text: str, kind: str) -> tuple[str, list[tuple[str, str]]] | None:
    matches = []
    for match in PAREN_SERIES_RE.finditer(text):
        label = match.group("label")
        if kind == "number" and label.isdigit():
            matches.append(match)
        elif kind == "alpha" and label.isalpha():
            matches.append(match)

    if not matches:
        return None

    prefix = clean_series_fragment(text[: matches[0].start()])
    items: list[tuple[str, str]] = []
    for idx, match in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        fragment = clean_series_fragment(text[match.end() : end])
        if fragment:
            items.append((match.group("label").lower(), fragment))

    if not items:
        return None
    return prefix, items


def extend_measure_suffix(items: list[tuple[str, str]]) -> list[tuple[str, str]]:
    suffix_source = next((text for _label, text in items if " of " in text.lower()), None)
    if suffix_source is None:
        return items

    lower_source = suffix_source.lower()
    suffix = suffix_source[lower_source.find(" of ") :]
    extended: list[tuple[str, str]] = []
    for label, text in items:
        if " of " not in text.lower() and MEASURE_HEAD_RE.match(text):
            extended.append((label, f"{text}{suffix}"))
        else:
            extended.append((label, text))
    return extended


def dedupe_texts(texts: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for text in texts:
        cleaned = clean_series_fragment(text)
        if not cleaned:
            continue
        normalized = cleaned.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(cleaned)
    return deduped


def build_title_datapoint_texts(title: str) -> list[str]:
    cleaned = clean_series_fragment(title)
    if not cleaned:
        return []

    cross_match = re.search(r"\bfor\s+\([a-z]\)", cleaned, flags=re.IGNORECASE)
    if cross_match:
        before = cleaned[: cross_match.start()].strip()
        after = cleaned[cross_match.start() + len("for ") :].strip()
        numeric_series = split_parenthetical_series(before, "number")
        alpha_series = split_parenthetical_series(after, "alpha")
        if numeric_series and alpha_series and len(numeric_series[1]) > 1 and len(alpha_series[1]) > 1:
            prefix, primary_items = numeric_series
            primary_items = extend_measure_suffix(primary_items)
            texts = [
                normalize_text(f"{prefix} {primary_text} for {secondary_text}".strip())
                for _primary_label, primary_text in primary_items
                for _secondary_label, secondary_text in alpha_series[1]
            ]
            return dedupe_texts(texts)

    numeric_series = split_parenthetical_series(cleaned, "number")
    if numeric_series and len(numeric_series[1]) > 1:
        prefix, items = numeric_series
        items = extend_measure_suffix(items)
        texts: list[str] = []
        for _label, item_text in items:
            candidate = normalize_text(f"{prefix} {item_text}".strip()) if prefix else item_text
            texts.append(candidate)
        return dedupe_texts(texts)

    alpha_series = split_parenthetical_series(cleaned, "alpha")
    if alpha_series and len(alpha_series[1]) > 1:
        prefix, items = alpha_series
        texts = [
            normalize_text(f"{prefix} {item_text}".strip()) if prefix else item_text
            for _label, item_text in items
        ]
        return dedupe_texts(texts)

    return [cleaned]


def extract_note_instruction(note_preface: list[str], note_clauses: list[NumberedClause]) -> list[str]:
    candidate_texts: list[str] = []
    candidate_texts.extend(note_preface)
    for clause in note_clauses[:1]:
        candidate_texts.append(clause.text)

    for candidate in candidate_texts:
        cleaned = clean_series_fragment(candidate)
        if not cleaned:
            continue
        normalized = re.sub(r"^the entity shall\s+", "", cleaned, flags=re.IGNORECASE)
        first_word = normalized.split(" ", 1)[0].lower()
        if first_word in DISALLOWED_NOTE_VERBS:
            return []
        if first_word in ALLOWED_NOTE_VERBS:
            expanded = [label for _code, label in expand_leaf_clause("note", normalized)]
            return dedupe_texts(expanded) or [normalized]

    return []


def infer_sasb_item_shape(label: str) -> tuple[str, str, str | None]:
    item_type, value_type, unit_code = infer_item_shape(label)
    normalized = normalize_text(label.lower())

    if normalized.startswith(
        (
            "discussion of",
            "description of",
            "list of",
            "approach to",
            "policies and practices",
            "policy",
            "methodology used",
            "use of",
            "explain",
            "describe",
            "disclose",
        )
    ):
        return "narrative", "text", None

    if "percentage" in normalized or "(%)" in normalized:
        return "metric", "number", "%"

    if any(
        marker in normalized
        for marker in ("monetary", "gross exposure", "amount of loans", "amount of past due", "amount of ")
    ):
        return "metric", "number", "CCY"

    if value_type == "number" and unit_code is None and normalized.startswith(
        ("number of ", "median ", "average ", "count of ", "total number of ")
    ):
        return "metric", "number", "COUNT"

    return item_type, value_type, unit_code


def make_datapoint(item_code: str, label: str) -> ParsedDataPoint:
    item_type, value_type, unit_code = infer_sasb_item_shape(label)
    return ParsedDataPoint(
        raw_code=item_code,
        item_code=item_code,
        label=label,
        item_type=item_type,
        value_type=value_type,
        unit_code=unit_code,
    )


def build_metric_datapoints(
    metric_code: str,
    metric_title: str,
    note_preface: list[str],
    note_clauses: list[NumberedClause],
) -> list[ParsedDataPoint]:
    title_labels = build_title_datapoint_texts(metric_title)
    note_labels = [
        label
        for label in extract_note_instruction(note_preface, note_clauses)
        if label.lower() not in {item.lower() for item in title_labels}
    ]

    datapoints: list[ParsedDataPoint] = []
    if len(title_labels) == 1 and not note_labels:
        return [make_datapoint(metric_code, title_labels[0])]

    for idx, label in enumerate(title_labels, start=1):
        datapoints.append(make_datapoint(f"{metric_code}.{idx}", label))
    for idx, label in enumerate(note_labels, start=1):
        datapoints.append(make_datapoint(f"{metric_code}.note.{idx}", label))
    return datapoints


def build_disclosure_blocks(
    *,
    topic_summary: str,
    requirements_preface: list[str],
    requirement_clauses: list[NumberedClause],
    table_blocks: list[dict],
    note_preface: list[str],
    note_clauses: list[NumberedClause],
    activity_note: str | None = None,
) -> list[dict]:
    blocks: list[dict] = []
    if topic_summary:
        blocks.append(
            {
                "type": "topic_summary",
                "title": "Topic Summary",
                "body_md": topic_summary,
                "paragraphs": topic_summary.split("\n\n"),
                "items": [],
            }
        )

    requirements_lines: list[str] = []
    if requirements_preface:
        requirements_lines.append("\n".join(requirements_preface))
    if requirement_clauses:
        requirements_lines.append("\n".join(clauses_to_markdown(requirement_clauses)))
    requirements_body = "\n".join(part for part in requirements_lines if part).strip()
    if requirements_body:
        blocks.append(
            {
                "type": "metrics",
                "title": "Metrics",
                "body_md": requirements_body,
                "paragraphs": [],
                "items": [],
                "metadata": {
                    "requirement_tree": [serialize_clause(clause) for clause in requirement_clauses],
                },
            }
        )

    blocks.extend(table_blocks)

    note_lines: list[str] = []
    if note_preface:
        note_lines.append("\n".join(note_preface))
    if note_clauses:
        note_lines.append("\n".join(clauses_to_markdown(note_clauses)))
    if activity_note:
        note_lines.append(activity_note)
    note_body = "\n".join(part for part in note_lines if part).strip()
    if note_body:
        blocks.append(
            {
                "type": "note",
                "title": "Note",
                "body_md": note_body,
                "paragraphs": [],
                "items": [],
                "metadata": {
                    "note_tree": [serialize_clause(clause) for clause in note_clauses],
                },
            }
        )

    return blocks


def parse_sasb_pdf(
    path: Path,
    *,
    standard_code: str | None = None,
    standard_name: str | None = None,
) -> SasbParsedStandard:
    lines = extract_pdf_lines(path)
    industry_name, industry_code, version = parse_standard_metadata(lines)
    resolved_standard_code, resolved_standard_name = resolve_standard_identity(
        industry_name,
        industry_code,
        standard_code=standard_code,
        standard_name=standard_name,
    )

    topic_ranges = find_topic_ranges(lines)
    if not topic_ranges:
        raise ValueError("Unable to locate SASB topic sections")

    disclosures: list[SasbParsedDisclosure] = []
    used_section_codes: set[str] = set()

    for section_sort_order, (topic_title, topic_start, topic_end) in enumerate(topic_ranges, start=1):
        section_code = topic_section_code(industry_code, topic_title, used_section_codes)
        concept_domain = concept_domain_from_title(topic_title)
        topic_summary = parse_topic_summary(lines, topic_start, topic_end)
        parsed_metrics = parse_topic_metrics(lines, topic_title, topic_start, topic_end)

        for disclosure_sort_order, (metric_code, metric_title, clause_lines, table_blocks, note_lines, _) in enumerate(parsed_metrics, start=1):
            requirements_preface, requirement_clauses = parse_numbered_clauses(clause_lines)
            note_preface, note_clauses = parse_numbered_clauses(note_lines)
            datapoints = build_metric_datapoints(metric_code, metric_title, note_preface, note_clauses)
            blocks = build_disclosure_blocks(
                topic_summary=topic_summary,
                requirements_preface=requirements_preface,
                requirement_clauses=requirement_clauses,
                table_blocks=table_blocks,
                note_preface=note_preface,
                note_clauses=note_clauses,
            )
            applicability_rule = {
                "source_format": "sasb_pdf_v2",
                "standard_family": "SASB",
                "industry_code": industry_code,
                "industry_title": industry_name,
                "metric_kind": "topic_metric",
                "content_blocks": blocks,
                "metric_meta": {
                    "section_code": section_code,
                    "section_title": topic_title,
                },
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
            parsed_disclosure = ParsedDisclosure(
                raw_code=metric_code,
                code=metric_code,
                title=metric_title,
                requirement_text=build_disclosure_description(blocks),
                requirement_type=infer_disclosure_type(datapoints),
                datapoints=datapoints,
                sort_order=disclosure_sort_order,
                applicability_rule=applicability_rule,
            )
            disclosures.append(
                SasbParsedDisclosure(
                    section_code=section_code,
                    section_title=topic_title,
                    section_sort_order=section_sort_order,
                    concept_domain=concept_domain,
                    disclosure=parsed_disclosure,
                )
            )

    activity_metrics = parse_activity_metrics(lines)
    if activity_metrics:
        activity_section_title = "Activity Metrics"
        activity_section_code = topic_section_code(industry_code, activity_section_title, used_section_codes)
        activity_concept_domain = concept_domain_from_title(activity_section_title)
        activity_sort_order = len(topic_ranges) + 1
        for disclosure_sort_order, (metric_code, metric_title, activity_note, _) in enumerate(activity_metrics, start=1):
            datapoints = build_metric_datapoints(metric_code, metric_title, [activity_note] if activity_note else [], [])
            blocks = build_disclosure_blocks(
                topic_summary="",
                requirements_preface=[],
                requirement_clauses=[],
                table_blocks=[],
                note_preface=[],
                note_clauses=[],
                activity_note=activity_note,
            )
            blocks.insert(
                0,
                {
                    "type": "activity_metric",
                    "title": "Activity Metric",
                    "body_md": metric_title,
                    "paragraphs": [metric_title],
                    "items": [],
                },
            )
            applicability_rule = {
                "source_format": "sasb_pdf_v2",
                "standard_family": "SASB",
                "industry_code": industry_code,
                "industry_title": industry_name,
                "metric_kind": "activity_metric",
                "content_blocks": blocks,
                "metric_meta": {
                    "section_code": activity_section_code,
                    "section_title": activity_section_title,
                },
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
            parsed_disclosure = ParsedDisclosure(
                raw_code=metric_code,
                code=metric_code,
                title=metric_title,
                requirement_text=build_disclosure_description(blocks),
                requirement_type=infer_disclosure_type(datapoints),
                datapoints=datapoints,
                sort_order=disclosure_sort_order,
                applicability_rule=applicability_rule,
            )
            disclosures.append(
                SasbParsedDisclosure(
                    section_code=activity_section_code,
                    section_title=activity_section_title,
                    section_sort_order=activity_sort_order,
                    concept_domain=activity_concept_domain,
                    disclosure=parsed_disclosure,
                )
            )

    return SasbParsedStandard(
        standard_code=resolved_standard_code,
        standard_name=resolved_standard_name,
        standard_version=version,
        jurisdiction="Global",
        disclosures=disclosures,
    )


async def upsert_standard(
    session: AsyncSession,
    *,
    code: str,
    name: str,
    version: str,
    jurisdiction: str,
) -> Standard:
    standard = (await session.execute(select(Standard).where(Standard.code == code))).scalar_one_or_none()
    if standard is None:
        standard = Standard(
            code=code,
            name=name,
            version=version,
            jurisdiction=jurisdiction,
            is_active=True,
        )
        session.add(standard)
        await session.flush()
        return standard

    changed = False
    if standard.name != name:
        standard.name = name
        changed = True
    if standard.version != version:
        standard.version = version
        changed = True
    if standard.jurisdiction != jurisdiction:
        standard.jurisdiction = jurisdiction
        changed = True
    if not standard.is_active:
        standard.is_active = True
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
        )
        session.add(section)
        await session.flush()
        stats.created_sections += 1
        return section

    changed = False
    if section.title != title:
        section.title = title
        changed = True
    if section.sort_order != sort_order:
        section.sort_order = sort_order
        changed = True
    if changed:
        await session.flush()
        stats.updated_sections += 1
    return section


async def import_sasb_pdf(
    session: AsyncSession,
    parsed: SasbParsedStandard,
    *,
    with_shared_elements: bool,
) -> ImportStats:
    stats = ImportStats()
    standard = await upsert_standard(
        session,
        code=parsed.standard_code,
        name=parsed.standard_name,
        version=parsed.standard_version,
        jurisdiction=parsed.jurisdiction,
    )

    section_cache: dict[str, StandardSection] = {}
    for entry in parsed.disclosures:
        section = section_cache.get(entry.section_code)
        if section is None:
            section = await upsert_section(
                session,
                standard_id=standard.id,
                code=entry.section_code,
                title=entry.section_title,
                sort_order=entry.section_sort_order,
                stats=stats,
            )
            section_cache[entry.section_code] = section

        disclosure_row = await upsert_disclosure(
            session,
            standard.id,
            section.id,
            entry.disclosure,
            stats,
        )

        active_item_codes: set[str] = set()
        for sort_order, datapoint in enumerate(entry.disclosure.datapoints, start=1):
            item = await upsert_requirement_item(
                session,
                disclosure_row.id,
                datapoint,
                sort_order,
                stats,
            )
            active_item_codes.add(datapoint.item_code)

            if with_shared_elements:
                element = await upsert_shared_element(session, item, entry.concept_domain, stats)
                await ensure_mapping(session, item.id, element.id, stats)

        await deactivate_stale_requirement_items(session, disclosure_row.id, active_item_codes)

    return stats


async def standard_exists(session: AsyncSession, code: str) -> bool:
    existing = await session.execute(select(Standard.id).where(Standard.code == code))
    return existing.scalar_one_or_none() is not None


async def run_import(
    path: Path,
    *,
    apply: bool,
    with_shared_elements: bool,
    standard_code: str | None,
    standard_name: str | None,
) -> SasbImportResult:
    parsed = parse_sasb_pdf(path, standard_code=standard_code, standard_name=standard_name)
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as session:
            stats = await import_sasb_pdf(
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

    return SasbImportResult(
        path=path,
        parsed=parsed,
        total_items=sum(len(entry.disclosure.datapoints) for entry in parsed.disclosures),
        stats=stats,
    )


async def run_batch_import(
    folder: Path,
    *,
    apply: bool,
    with_shared_elements: bool,
    skip_existing: bool,
) -> list[SasbBatchEntry]:
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    results: list[SasbBatchEntry] = []
    pdf_paths = sorted(folder.glob("*.pdf"))

    try:
        for path in pdf_paths:
            try:
                standard_code, standard_name = peek_sasb_identity(
                    path,
                    standard_code=None,
                    standard_name=None,
                )

                async with session_factory() as session:
                    if skip_existing and await standard_exists(session, standard_code):
                        results.append(
                            SasbBatchEntry(
                                path=path,
                                standard_code=standard_code,
                                standard_name=standard_name,
                                status="skipped",
                                message="standard already exists",
                            )
                        )
                        continue

                parsed = parse_sasb_pdf(path, standard_code=standard_code, standard_name=standard_name)
                async with session_factory() as session:
                    stats = await import_sasb_pdf(
                        session,
                        parsed,
                        with_shared_elements=with_shared_elements,
                    )
                    if apply:
                        await session.commit()
                    else:
                        await session.rollback()

                results.append(
                    SasbBatchEntry(
                        path=path,
                        standard_code=parsed.standard_code,
                        standard_name=parsed.standard_name,
                        status="imported",
                        disclosures=len(parsed.disclosures),
                        datapoints=sum(len(entry.disclosure.datapoints) for entry in parsed.disclosures),
                        stats=stats,
                    )
                )
            except Exception as exc:
                results.append(
                    SasbBatchEntry(
                        path=path,
                        standard_code="",
                        standard_name=path.stem,
                        status="failed",
                        message=str(exc),
                    )
                )
    finally:
        await engine.dispose()

    return results


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import SASB PDF standards into the framework catalog.")
    parser.add_argument("input_path", type=Path, help="Path to a SASB PDF file or a folder containing SASB PDFs.")
    parser.add_argument(
        "--standard-code",
        default=None,
        help="Optional framework code override for single-file imports.",
    )
    parser.add_argument(
        "--standard-name",
        default=None,
        help="Optional display name override for single-file imports.",
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
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip standards that already exist in the global catalog. Useful for folder batch runs.",
    )
    return parser


def print_single_result(result: SasbImportResult, *, mode: str) -> None:
    print(f"Input:       {result.path}")
    print(f"Mode:        {mode}")
    print(f"Standard:    {result.parsed.standard_code} - {result.parsed.standard_name}")
    print(f"Version:     {result.parsed.standard_version}")
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


def print_batch_results(results: list[SasbBatchEntry], *, mode: str, folder: Path) -> None:
    imported = [result for result in results if result.status == "imported"]
    skipped = [result for result in results if result.status == "skipped"]
    failed = [result for result in results if result.status == "failed"]
    total_disclosures = sum(result.disclosures for result in imported)
    total_datapoints = sum(result.datapoints for result in imported)

    print(f"Input:       {folder}")
    print(f"Mode:        {mode}")
    print(f"Files:       {len(results)}")
    print(f"Imported:    {len(imported)}")
    print(f"Skipped:     {len(skipped)}")
    print(f"Failed:      {len(failed)}")
    print(f"Disclosures: {total_disclosures}")
    print(f"DataPoints:  {total_datapoints}")
    if skipped:
        print("Skipped standards")
        for result in skipped:
            print(f"  - {result.standard_code or result.path.name}: {result.message}")
    if failed:
        print("Failed standards")
        for result in failed:
            print(f"  - {result.path.name}: {result.message}")


async def async_main(args: argparse.Namespace) -> int:
    with_shared_elements = not args.no_shared_elements
    mode = "apply" if args.apply else "dry-run"

    if args.input_path.is_dir():
        results = await run_batch_import(
            args.input_path,
            apply=args.apply,
            with_shared_elements=with_shared_elements,
            skip_existing=args.skip_existing,
        )
        print_batch_results(results, mode=mode, folder=args.input_path)
        return 0 if not any(result.status == "failed" for result in results) else 1

    result = await run_import(
        args.input_path,
        apply=args.apply,
        with_shared_elements=with_shared_elements,
        standard_code=args.standard_code,
        standard_name=args.standard_name,
    )
    print_single_result(result, mode=mode)
    return 0


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    return asyncio.run(async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
