"""
Minimal valid block payloads (v2) for schema↔template and preview smoke tests.

Design goals:
- Use ONLY schema-defined keys where possible (to catch template/schema drift)
- Keep payloads small but realistic enough to exercise rendering paths
- Provide one payload per block type, plus:
  - 4 table modes (builder/advanced/custom/image)
  - 8 chart types (bar/line/area/stacked/pie/donut/timeseries/scenario)
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from app.domain.models.enums import BlockType, BlockVariant


@dataclass(frozen=True)
class BlockPayload:
    name: str
    block_type: BlockType
    variant: BlockVariant = BlockVariant.DEFAULT
    data_json: dict = None  # type: ignore[assignment]
    fields_json: dict = None  # type: ignore[assignment]
    # Optional non-fields properties stored on BlockI18n (used by custom blocks)
    custom_html_sanitized: str | None = None


def _uuid() -> str:
    return str(uuid4())


ASSET_ID_1 = _uuid()
ASSET_ID_2 = _uuid()
ASSET_ID_3 = _uuid()


# === Non-chart, non-table blocks ===

TEXT_BLOCK = BlockPayload(
    name="text",
    block_type=BlockType.TEXT,
    data_json={},
    fields_json={"body_html": "<p>Test text block</p>"},
)

QUOTE_BLOCK = BlockPayload(
    name="quote",
    block_type=BlockType.QUOTE,
    data_json={},
    fields_json={
        "quote_text": "Data quality matters more than data volume.",
        "author_name": "ESG Team",
        "author_title": "Internal reporting standard",
    },
)

IMAGE_BLOCK = BlockPayload(
    name="image",
    block_type=BlockType.IMAGE,
    data_json={"asset_id": ASSET_ID_1, "layout": "full"},
    fields_json={"caption": "Figure — sample image", "alt_text": "Sample image"},
)

DOWNLOADS_BLOCK = BlockPayload(
    name="downloads",
    block_type=BlockType.DOWNLOADS,
    data_json={
        "layout": "list",
        "items": [
            {"asset_id": ASSET_ID_2, "file_type": "pdf", "order": 0},
        ],
    },
    fields_json={
        "title": "Downloads",
        "items": [{"label": "Sustainability policy (PDF)", "description": "Current version"}],
    },
)

CUSTOM_BLOCK = BlockPayload(
    name="custom",
    block_type=BlockType.CUSTOM,
    data_json={"html": "<div><strong>Custom</strong> HTML</div>", "sandbox_level": "strict"},
    fields_json={"caption": "Custom block", "insight_text": "Custom block description"},
    # Renderer/template uses this field (not fields_json) for preview rendering
    custom_html_sanitized="<div><strong>Custom</strong> HTML</div>",
)

KPI_CARDS_BLOCK = BlockPayload(
    name="kpi_cards",
    block_type=BlockType.KPI_CARDS,
    variant=BlockVariant.EMPHASIZED,
    data_json={
        "items": [
            {"value": 25.2, "unit": "ktU", "period": "2024", "trend": "up"},
            {"value": 22, "unit": "%", "period": "2024", "trend": "stable"},
        ]
    },
    fields_json={
        "title": "Key metrics",
        "items": [
            {"label": "Uranium production", "note": "Including joint ventures"},
            {"label": "Market share", "note": "Estimate based on global production"},
        ],
    },
)

ACCORDION_BLOCK = BlockPayload(
    name="accordion",
    block_type=BlockType.ACCORDION,
    data_json={
        "allow_multiple": False,
        "items": [
            {"key": "q1", "default_open": True},
            {"key": "q2", "default_open": False},
        ],
    },
    fields_json={
        "title": "FAQ",
        "items": [
            {"title": "How is the data prepared?", "content_html": "<p>From accounting and verification sources.</p>"},
            {"title": "How often is the report updated?", "content_html": "<p>Annually.</p>"},
        ],
    },
)

TIMELINE_BLOCK = BlockPayload(
    name="timeline",
    block_type=BlockType.TIMELINE,
    data_json={
        "layout": "vertical",
        "items": [
            {"date": "January 2024", "icon": None},
            {"date": "July 2024", "icon": None},
        ],
    },
    fields_json={
        "title": "Key events",
        "items": [
            {"title": "New site launched", "description": "Capacity commissioned using ISR."},
            {"title": "Supply contract", "description": "Signed a long-term contract."},
        ],
    },
)

# Legacy format: events as dict keyed by event_id (from seed data)
TIMELINE_BLOCK_LEGACY_DICT = BlockPayload(
    name="timeline_legacy_dict",
    block_type=BlockType.TIMELINE,
    data_json={
        "events": [
            {"event_id": "evt_2024_01", "date_start": "2024", "date_format": "year"},
            {"event_id": "evt_2024_07", "date_start": "2024-07", "date_format": "month"},
        ],
        "auto_sort": True,
    },
    fields_json={
        "title": "Key milestones",
        "events": {
            "evt_2024_01": {"title": "Event A", "description": "Event A description"},
            "evt_2024_07": {"title": "Event B", "description": "Event B description"},
        },
    },
)


# === Table payloads (4 modes) ===

TABLE_BUILDER_BLOCK = BlockPayload(
    name="table_builder",
    block_type=BlockType.TABLE,
    data_json={
        "mode": "builder",
        "columns": [
            {"key": "metric", "type": "text", "align": "left"},
            {"key": "value", "type": "number", "align": "right"},
        ],
        "rows": [
            {"cells": {"metric": "Revenue", "value": 847.3}, "is_header": False, "is_total": False},
            {"cells": {"metric": "EBITDA", "value": 324.5}, "is_header": False, "is_total": False},
        ],
        "striped": True,
    },
    fields_json={
        "caption": "Table — financial metrics",
        "summary": "Builder mode table example",
        "column_labels": {"metric": "Metric", "value": "Value"},
    },
)

TABLE_ADVANCED_BLOCK = BlockPayload(
    name="table_advanced",
    block_type=BlockType.TABLE,
    data_json={
        "mode": "advanced",
        "columns": [
            {"key": "name", "type": "text", "align": "left"},
            {"key": "val", "type": "number", "align": "right"},
        ],
    },
    fields_json={
        "caption": "Table — advanced (preview placeholder)",
        "summary": "In preview, advanced tables render a placeholder",
        "column_labels": {"name": "Metric", "val": "Value"},
    },
)

TABLE_CUSTOM_BLOCK = BlockPayload(
    name="table_custom",
    block_type=BlockType.TABLE,
    data_json={
        "mode": "custom",
        "custom_html": "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>",
    },
    fields_json={
        "caption": "Table — custom HTML",
        "summary": "Table rendered from custom_html",
    },
)

TABLE_IMAGE_BLOCK = BlockPayload(
    name="table_image",
    block_type=BlockType.TABLE,
    data_json={
        "mode": "image",
        "asset_id": ASSET_ID_3,
    },
    fields_json={
        "caption": "Table — image",
        "summary": "Table rendered as an image",
        "alt_text": "Table screenshot",
    },
)


# === Chart payloads (8 types) ===

def _chart_payload(chart_type: str, columns: list[str], rows: list[list], x_field: str, x_type: str, series: list[dict], *, caption: str) -> BlockPayload:
    return BlockPayload(
        name=f"chart_{chart_type}",
        block_type=BlockType.CHART,
        data_json={
            "chart_type": chart_type,
            "data_source": {"type": "inline", "inline_data": {"columns": columns, "rows": rows}},
            "mapping": {"x": {"field": x_field, "type": x_type}, "series": series},
            "options": {"show_legend": True, "show_grid": True},
        },
        fields_json={
            "caption": caption,
            "insight_text": "Test chart description for preview.",
            "source": "Test data",
        },
    )


CHARTS = [
    _chart_payload(
        "bar",
        ["Category", "Value"],
        [["A", 10], ["B", 20], ["C", 15]],
        "Category",
        "category",
        [{"name": "Value", "y_field": "Value", "axis": "left"}],
        caption="Bar — test chart",
    ),
    _chart_payload(
        "line",
        ["Year", "Revenue"],
        [["2022", 673.2], ["2023", 712.4], ["2024", 847.3]],
        "Year",
        "category",
        [{"name": "Revenue", "y_field": "Revenue", "axis": "left"}],
        caption="Line — test chart",
    ),
    _chart_payload(
        "area",
        ["Quarter", "Production"],
        [["Q1", 6.3], ["Q2", 6.7], ["Q3", 6.4], ["Q4", 5.8]],
        "Quarter",
        "category",
        [{"name": "Production", "y_field": "Production", "axis": "left"}],
        caption="Area — test chart",
    ),
    _chart_payload(
        "stacked",
        ["Year", "CapEx", "OpEx"],
        [["2022", 142.3, 426.5], ["2023", 155.7, 447.3], ["2024", 178.6, 522.8]],
        "Year",
        "category",
        [
            {"name": "CapEx", "y_field": "CapEx", "axis": "left", "stack_group": "costs"},
            {"name": "OpEx", "y_field": "OpEx", "axis": "left", "stack_group": "costs"},
        ],
        caption="Stacked — test chart",
    ),
    _chart_payload(
        "pie",
        ["Segment", "Share"],
        [["A", 55], ["B", 30], ["C", 15]],
        "Segment",
        "category",
        [{"name": "Share", "y_field": "Share", "axis": "left"}],
        caption="Pie — test chart",
    ),
    _chart_payload(
        "donut",
        ["Category", "Emissions"],
        [["Scope 1", 892], ["Scope 2", 693], ["Scope 3", 396]],
        "Category",
        "category",
        [{"name": "Emissions", "y_field": "Emissions", "axis": "left"}],
        caption="Donut — test chart",
    ),
    _chart_payload(
        "timeseries",
        ["Date", "Price"],
        [["2024-01-01", 21500], ["2024-02-01", 22100], ["2024-03-01", 22800]],
        "Date",
        "date",
        [{"name": "Price", "y_field": "Price", "axis": "left"}],
        caption="Timeseries — test chart",
    ),
    _chart_payload(
        "scenario",
        ["Year", "Base", "Optimistic", "Conservative"],
        [["2024", 25.0, 25.0, 25.0], ["2025", 26.5, 28.0, 25.2], ["2026", 27.3, 30.1, 25.0]],
        "Year",
        "category",
        [
            {"name": "Base", "y_field": "Base", "axis": "left"},
            {"name": "Optimistic", "y_field": "Optimistic", "axis": "left"},
            {"name": "Conservative", "y_field": "Conservative", "axis": "left"},
        ],
        caption="Scenario — test chart",
    ),
]


ALL_BLOCK_PAYLOADS: list[BlockPayload] = [
    TEXT_BLOCK,
    KPI_CARDS_BLOCK,
    QUOTE_BLOCK,
    IMAGE_BLOCK,
    DOWNLOADS_BLOCK,
    ACCORDION_BLOCK,
    TIMELINE_BLOCK,
    TIMELINE_BLOCK_LEGACY_DICT,
    CUSTOM_BLOCK,
    TABLE_BUILDER_BLOCK,
    TABLE_ADVANCED_BLOCK,
    TABLE_CUSTOM_BLOCK,
    TABLE_IMAGE_BLOCK,
    *CHARTS,
]
