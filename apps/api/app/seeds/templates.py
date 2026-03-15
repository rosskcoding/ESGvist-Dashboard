"""
Seed data for built-in templates.

Run with: python -m app.seeds.templates
"""

from uuid import uuid4

# ============================================================
# KPI Templates
# ============================================================

KPI_COMPANY_IN_NUMBERS = {
    "template_id": str(uuid4()),
    "scope": "block",
    "block_type": "kpi_cards",
    "name": "Company in Numbers",
    "description": "Standard 6-card layout for key company metrics",
    "tags": ["kpi", "overview", "executive"],
    "is_system": True,
    "template_json": {
        "variant": "default",
        "data_json": {
            "schema_version": 2,
            "items": [
                {"item_id": "kpi-1", "value": 0, "unit": "bn KZT", "period": "2024"},
                {"item_id": "kpi-2", "value": 0, "unit": "%", "period": "2024"},
                {"item_id": "kpi-3", "value": 0, "unit": "k", "period": "2024"},
                {"item_id": "kpi-4", "value": 0, "unit": "", "period": "2024"},
                {"item_id": "kpi-5", "value": 0, "unit": "m", "period": "2024"},
                {"item_id": "kpi-6", "value": 0, "unit": "", "period": "2024"},
            ],
        },
        "fields_json": {
            "title": "Company in Numbers",
            "template_id": "company_in_numbers",
            "items": [
                {"label": "Revenue"},
                {"label": "Profitability"},
                {"label": "Employees"},
                {"label": "Projects"},
                {"label": "Investments"},
                {"label": "Regions"},
            ],
        },
    },
}

KPI_CLIMATE = {
    "template_id": str(uuid4()),
    "scope": "block",
    "block_type": "kpi_cards",
    "name": "Climate KPIs",
    "description": "Environmental metrics: emissions, energy, renewables",
    "tags": ["kpi", "climate", "esg", "environment"],
    "is_system": True,
    "template_json": {
        "variant": "default",
        "data_json": {
            "schema_version": 2,
            "items": [
                {"item_id": "scope1", "value": 0, "unit": "tCO2e", "period": "2024"},
                {"item_id": "scope2", "value": 0, "unit": "tCO2e", "period": "2024"},
                {"item_id": "scope3", "value": 0, "unit": "tCO2e", "period": "2024"},
                {"item_id": "intensity", "value": 0, "unit": "tCO2e/m KZT", "period": "2024"},
                {"item_id": "renewables", "value": 0, "unit": "%", "period": "2024"},
                {"item_id": "energy", "value": 0, "unit": "GJ", "period": "2024"},
            ],
        },
        "fields_json": {
            "title": "Climate and Environment",
            "template_id": "climate",
            "items": [
                {"label": "Scope 1 emissions"},
                {"label": "Scope 2 emissions"},
                {"label": "Scope 3 emissions"},
                {"label": "Carbon intensity"},
                {"label": "Renewable energy"},
                {"label": "Energy consumption"},
            ],
        },
    },
}

KPI_HSE = {
    "template_id": str(uuid4()),
    "scope": "block",
    "block_type": "kpi_cards",
    "name": "HSE KPIs",
    "description": "Health, Safety & Environment metrics",
    "tags": ["kpi", "hse", "safety", "health"],
    "is_system": True,
    "template_json": {
        "variant": "default",
        "data_json": {
            "schema_version": 2,
            "items": [
                {"item_id": "ltifr", "value": 0, "unit": "", "period": "2024"},
                {"item_id": "trir", "value": 0, "unit": "", "period": "2024"},
                {"item_id": "fatalities", "value": 0, "unit": "", "period": "2024"},
                {"item_id": "training", "value": 0, "unit": "hours", "period": "2024"},
            ],
        },
        "fields_json": {
            "title": "Health and Safety",
            "template_id": "hse",
            "items": [
                {"label": "LTIFR"},
                {"label": "TRIR"},
                {"label": "Fatalities"},
                {"label": "Safety training"},
            ],
        },
    },
}

KPI_PEOPLE = {
    "template_id": str(uuid4()),
    "scope": "block",
    "block_type": "kpi_cards",
    "name": "People KPIs",
    "description": "HR and workforce metrics",
    "tags": ["kpi", "people", "hr", "social"],
    "is_system": True,
    "template_json": {
        "variant": "default",
        "data_json": {
            "schema_version": 2,
            "items": [
                {"item_id": "headcount", "value": 0, "unit": "people", "period": "2024"},
                {"item_id": "turnover", "value": 0, "unit": "%", "period": "2024"},
                {"item_id": "women", "value": 0, "unit": "%", "period": "2024"},
                {"item_id": "training_hours", "value": 0, "unit": "hours/person", "period": "2024"},
            ],
        },
        "fields_json": {
            "title": "People",
            "template_id": "people",
            "items": [
                {"label": "Headcount"},
                {"label": "Turnover"},
                {"label": "Women share"},
                {"label": "Training"},
            ],
        },
    },
}

# ============================================================
# Chart Templates
# ============================================================

CHART_TREND_3_YEAR = {
    "template_id": str(uuid4()),
    "scope": "block",
    "block_type": "chart",
    "name": "3-Year Trend",
    "description": "Line chart showing 3-year trend of a metric",
    "tags": ["chart", "trend", "line"],
    "is_system": True,
    "template_json": {
        "variant": "default",
        "data_json": {
            "schema_version": 2,
            "chart_type": "line",
            "data_source": {
                "type": "inline",
                "inline_data": {
                    "columns": ["year", "value"],
                    "rows": [
                        ["2022", 0],
                        ["2023", 0],
                        ["2024", 0],
                    ],
                },
            },
            "mapping": {
                "x": {"field": "year", "type": "date"},
                "series": [{"name": "Value", "y_field": "value", "axis": "left"}],
            },
            "options": {
                "show_legend": True,
                "show_grid": True,
                "show_values": True,
            },
        },
        "fields_json": {
            "caption": "[[AUTO:FIGURE_LABEL]] — 3-year trend",
            "insight_text": "The chart shows the metric trend over the last 3 years.",
            "unit": "",
        },
    },
}

CHART_YOY_BAR = {
    "template_id": str(uuid4()),
    "scope": "block",
    "block_type": "chart",
    "name": "YoY Bar Chart",
    "description": "Bar chart comparing year-over-year performance",
    "tags": ["chart", "bar", "comparison"],
    "is_system": True,
    "template_json": {
        "variant": "default",
        "data_json": {
            "schema_version": 2,
            "chart_type": "bar",
            "data_source": {
                "type": "inline",
                "inline_data": {
                    "columns": ["category", "2023", "2024"],
                    "rows": [
                        ["Q1", 0, 0],
                        ["Q2", 0, 0],
                        ["Q3", 0, 0],
                        ["Q4", 0, 0],
                    ],
                },
            },
            "mapping": {
                "x": {"field": "category", "type": "category"},
                "series": [
                    {"name": "2023", "y_field": "2023", "axis": "left"},
                    {"name": "2024", "y_field": "2024", "axis": "left"},
                ],
            },
            "options": {
                "show_legend": True,
                "show_grid": True,
            },
        },
        "fields_json": {
            "caption": "[[AUTO:FIGURE_LABEL]] — YoY comparison",
            "insight_text": "The bar chart compares results for 2023 and 2024 by quarter.",
            "unit": "",
        },
    },
}

CHART_STACKED = {
    "template_id": str(uuid4()),
    "scope": "block",
    "block_type": "chart",
    "name": "Stacked Composition",
    "description": "Stacked bar chart showing composition breakdown",
    "tags": ["chart", "stacked", "composition"],
    "is_system": True,
    "template_json": {
        "variant": "default",
        "data_json": {
            "schema_version": 2,
            "chart_type": "stacked",
            "data_source": {
                "type": "inline",
                "inline_data": {
                    "columns": ["year", "category1", "category2", "category3"],
                    "rows": [
                        ["2022", 30, 50, 20],
                        ["2023", 35, 45, 20],
                        ["2024", 40, 40, 20],
                    ],
                },
            },
            "mapping": {
                "x": {"field": "year", "type": "date"},
                "series": [
                    {"name": "Category 1", "y_field": "category1", "axis": "left", "stack_group": "main"},
                    {"name": "Category 2", "y_field": "category2", "axis": "left", "stack_group": "main"},
                    {"name": "Category 3", "y_field": "category3", "axis": "left", "stack_group": "main"},
                ],
            },
            "options": {
                "show_legend": True,
                "stacked": True,
            },
        },
        "fields_json": {
            "caption": "[[AUTO:FIGURE_LABEL]] — Composition by category",
            "insight_text": "The chart shows the composition by category over the last 3 years.",
            "unit": "",
        },
    },
}

CHART_PIE = {
    "template_id": str(uuid4()),
    "scope": "block",
    "block_type": "chart",
    "name": "Pie/Donut Chart",
    "description": "Pie chart for share/distribution visualization",
    "tags": ["chart", "pie", "share"],
    "is_system": True,
    "template_json": {
        "variant": "default",
        "data_json": {
            "schema_version": 2,
            "chart_type": "donut",
            "data_source": {
                "type": "inline",
                "inline_data": {
                    "columns": ["category", "value"],
                    "rows": [
                        ["Segment A", 40],
                        ["Segment B", 30],
                        ["Segment C", 20],
                        ["Other", 10],
                    ],
                },
            },
            "mapping": {
                "x": {"field": "category", "type": "category"},
                "series": [{"name": "Share", "y_field": "value", "axis": "left"}],
            },
            "options": {
                "show_legend": True,
                "show_values": True,
            },
        },
        "fields_json": {
            "caption": "[[AUTO:FIGURE_LABEL]] — Distribution by segment",
            "insight_text": "The chart shows distribution by segment.",
            "unit": "%",
        },
    },
}

# ============================================================
# Table Templates
# ============================================================

TABLE_ESG_METRICS = {
    "template_id": str(uuid4()),
    "scope": "block",
    "block_type": "table",
    "name": "ESG Metrics Table",
    "description": "3-year ESG metrics table with units and trends",
    "tags": ["table", "esg", "metrics"],
    "is_system": True,
    "template_json": {
        "variant": "default",
        "data_json": {
            "schema_version": 1,
            "columns": [
                {"key": "metric", "header": "Metric", "type": "text", "width": 200},
                {"key": "unit", "header": "Unit", "type": "text", "width": 80},
                {"key": "y2022", "header": "2022", "type": "number", "width": 100},
                {"key": "y2023", "header": "2023", "type": "number", "width": 100},
                {"key": "y2024", "header": "2024", "type": "number", "width": 100},
            ],
            "rows": [
                {"metric": "[[METRIC_NAME]]", "unit": "", "y2022": None, "y2023": None, "y2024": None},
            ],
        },
        "fields_json": {
            "title": "ESG metrics",
            "caption": "[[AUTO:TABLE_LABEL]] — ESG metrics trend",
            "notes": "[1] Data shown for the Group\n[2] Source: management reporting",
        },
    },
}

TABLE_GRI_INDEX = {
    "template_id": str(uuid4()),
    "scope": "block",
    "block_type": "table",
    "name": "GRI Index Table",
    "description": "GRI Content Index reference table",
    "tags": ["table", "gri", "index", "standards"],
    "is_system": True,
    "template_json": {
        "variant": "default",
        "data_json": {
            "schema_version": 1,
            "columns": [
                {"key": "code", "header": "Code", "type": "text", "width": 100},
                {"key": "topic", "header": "Disclosure topic", "type": "text", "width": 250},
                {"key": "location", "header": "Where disclosed", "type": "text", "width": 200},
                {"key": "page", "header": "Page", "type": "number", "width": 60},
            ],
            "rows": [
                {"code": "2-1", "topic": "Organizational details", "location": "[[SECTION]]", "page": None},
                {"code": "2-2", "topic": "Reporting scope", "location": "[[SECTION]]", "page": None},
            ],
        },
        "fields_json": {
            "title": "GRI Index",
            "caption": "[[AUTO:TABLE_LABEL]] — GRI Content Index",
            "notes": "",
        },
    },
}

TABLE_TARGETS = {
    "template_id": str(uuid4()),
    "scope": "block",
    "block_type": "table",
    "name": "Targets & Progress",
    "description": "Strategic targets with baseline, current, and target values",
    "tags": ["table", "targets", "progress"],
    "is_system": True,
    "template_json": {
        "variant": "default",
        "data_json": {
            "schema_version": 1,
            "columns": [
                {"key": "goal", "header": "Goal", "type": "text", "width": 200},
                {"key": "baseline", "header": "Baseline year", "type": "text", "width": 100},
                {"key": "current", "header": "Current", "type": "text", "width": 100},
                {"key": "target", "header": "Target", "type": "text", "width": 100},
                {"key": "status", "header": "Status", "type": "text", "width": 100},
            ],
            "rows": [
                {"goal": "[[GOAL]]", "baseline": "2022: —", "current": "2024: —", "target": "2030: —", "status": "◐ In progress"},
            ],
        },
        "fields_json": {
            "title": "Goals and progress",
            "caption": "[[AUTO:TABLE_LABEL]] — Progress on strategic goals",
            "notes": "",
        },
    },
}

# ============================================================
# Timeline Templates
# ============================================================

TIMELINE_KEY_EVENTS = {
    "template_id": str(uuid4()),
    "scope": "block",
    "block_type": "timeline",
    "name": "Key Events",
    "description": "Timeline of key events by month",
    "tags": ["timeline", "events", "history"],
    "is_system": True,
    "template_json": {
        "variant": "default",
        "data_json": {
            "schema_version": 2,
            "events": [
                {"event_id": "evt-1", "date_start": "2024-01", "date_kind": "month", "status": "done"},
                {"event_id": "evt-2", "date_start": "2024-04", "date_kind": "month", "status": "done"},
                {"event_id": "evt-3", "date_start": "2024-07", "date_kind": "month", "status": "in_progress"},
                {"event_id": "evt-4", "date_start": "2024-10", "date_kind": "month", "status": "planned"},
            ],
            "orientation": "vertical",
            "auto_sort_by_date": True,
        },
        "fields_json": {
            "title": "Key events 2024",
            "events": [
                {"title": "Event 1", "description": "Event description"},
                {"title": "Event 2", "description": "Event description"},
                {"title": "Event 3", "description": "Event description"},
                {"title": "Event 4", "description": "Event description"},
            ],
        },
    },
}

TIMELINE_ROADMAP = {
    "template_id": str(uuid4()),
    "scope": "block",
    "block_type": "timeline",
    "name": "Roadmap",
    "description": "Quarterly roadmap with status indicators",
    "tags": ["timeline", "roadmap", "strategy"],
    "is_system": True,
    "template_json": {
        "variant": "default",
        "data_json": {
            "schema_version": 2,
            "events": [
                {"event_id": "q1", "date_start": "2024-Q1", "date_kind": "quarter", "status": "done", "tags": ["Phase 1"]},
                {"event_id": "q2", "date_start": "2024-Q2", "date_kind": "quarter", "status": "done", "tags": ["Phase 1"]},
                {"event_id": "q3", "date_start": "2024-Q3", "date_kind": "quarter", "status": "in_progress", "tags": ["Phase 2"]},
                {"event_id": "q4", "date_start": "2024-Q4", "date_kind": "quarter", "status": "planned", "tags": ["Phase 2"]},
            ],
            "orientation": "horizontal",
            "auto_sort_by_date": False,
        },
        "fields_json": {
            "title": "Roadmap 2024",
            "events": [
                {"title": "Q1 2024", "description": "[[MILESTONE_1]]"},
                {"title": "Q2 2024", "description": "[[MILESTONE_2]]"},
                {"title": "Q3 2024", "description": "[[MILESTONE_3]]"},
                {"title": "Q4 2024", "description": "[[MILESTONE_4]]"},
            ],
        },
    },
}

# ============================================================
# NEW TEMPLATES (with ASK/AUTO/OPT placeholders)
# ============================================================

# --- Quote Templates ---

CEO_MESSAGE = {
    "template_id": str(uuid4()),
    "scope": "block",
    "block_type": "quote",
    "name": "CEO Message",
    "description": "Executive message with photo and title",
    "tags": ["quote", "leadership", "executive", "message"],
    "is_system": True,
    "template_json": {
        "variant": "emphasized",
        "data_json": {
            "schema_version": 2,
            "author_photo_asset_id": None,  # [[OPT:AUTHOR_PHOTO]]
        },
        "fields_json": {
            "quote_text": "[[ASK:MESSAGE_TEXT]]",
            "author_name": "[[ASK:AUTHOR_NAME]]",
            "author_title": "[[ASK:AUTHOR_TITLE]]",
        },
    },
}

# --- Text Templates ---

CALLOUT_BOX = {
    "template_id": str(uuid4()),
    "scope": "block",
    "block_type": "text",
    "name": "Callout Box",
    "description": "Highlighted information box with optional icon",
    "tags": ["text", "callout", "highlight", "info"],
    "is_system": True,
    "template_json": {
        "variant": "emphasized",
        "data_json": {
            "schema_version": 2,
        },
        "fields_json": {
            "title": "[[AUTO:BOX_LABEL]] — [[ASK:BOX_TITLE]]",
            "content": "[[ASK:BOX_CONTENT]]",
        },
    },
}

# --- Downloads Templates ---

DOWNLOADS_SECTION = {
    "template_id": str(uuid4()),
    "scope": "block",
    "block_type": "downloads",
    "name": "Downloads Section",
    "description": "List of downloadable documents and files",
    "tags": ["downloads", "documents", "files"],
    "is_system": True,
    "template_json": {
        "variant": "default",
        "data_json": {
            "schema_version": 2,
            "items": [],  # User will add files
        },
        "fields_json": {
            "title": "[[ASK:SECTION_TITLE]]",
            "description": "[[OPT:DESCRIPTION]]",
        },
    },
}

# --- Chart Templates (New) ---

CHART_EMISSIONS_BY_SCOPE = {
    "template_id": str(uuid4()),
    "scope": "block",
    "block_type": "chart",
    "name": "Emissions by Scope",
    "description": "Pie chart showing greenhouse gas emissions breakdown by scope",
    "tags": ["chart", "pie", "emissions", "climate", "ghg"],
    "is_system": True,
    "template_json": {
        "variant": "default",
        "data_json": {
            "schema_version": 2,
            "chart_type": "donut",
            "data_source": {
                "type": "inline",
                "inline_data": {
                    "columns": ["scope", "emissions"],
                    "rows": [
                        ["Scope 1", 0],
                        ["Scope 2", 0],
                        ["Scope 3", 0],
                    ],
                },
            },
            "mapping": {
                "x": {"field": "scope", "type": "category"},
                "series": [{"name": "Emissions", "y_field": "emissions", "axis": "left"}],
            },
            "options": {
                "show_legend": True,
                "show_values": True,
            },
        },
        "fields_json": {
            "caption": "[[AUTO:FIGURE_LABEL]] — Emissions by category for [[ASK:PERIOD]]",
            "insight_text": "Breakdown of greenhouse gas emissions by scope.",
            "unit": "tCO2e",
            "source": "[[OPT:SOURCE]]",
        },
    },
}

CHART_WATER_USAGE = {
    "template_id": str(uuid4()),
    "scope": "block",
    "block_type": "chart",
    "name": "Water Usage Trend",
    "description": "Bar chart showing water consumption over time",
    "tags": ["chart", "bar", "water", "environment", "resources"],
    "is_system": True,
    "template_json": {
        "variant": "default",
        "data_json": {
            "schema_version": 2,
            "chart_type": "bar",
            "data_source": {
                "type": "inline",
                "inline_data": {
                    "columns": ["year", "consumption"],
                    "rows": [
                        ["2022", 0],
                        ["2023", 0],
                        ["2024", 0],
                    ],
                },
            },
            "mapping": {
                "x": {"field": "year", "type": "date"},
                "series": [{"name": "Water Usage", "y_field": "consumption", "axis": "left"}],
            },
            "options": {
                "show_legend": False,
                "show_grid": True,
                "show_values": True,
            },
        },
        "fields_json": {
            "caption": "[[AUTO:FIGURE_LABEL]] — Water use for [[ASK:PERIOD]]",
            "insight_text": "Trend of the company's water use.",
            "unit": "[[OPT:UNIT]]",
            "source": "[[OPT:SOURCE]]",
        },
    },
}

CHART_ENERGY_MIX = {
    "template_id": str(uuid4()),
    "scope": "block",
    "block_type": "chart",
    "name": "Energy Mix",
    "description": "Donut chart showing energy sources distribution",
    "tags": ["chart", "donut", "energy", "renewables", "climate"],
    "is_system": True,
    "template_json": {
        "variant": "default",
        "data_json": {
            "schema_version": 2,
            "chart_type": "donut",
            "data_source": {
                "type": "inline",
                "inline_data": {
                    "columns": ["source", "share"],
                    "rows": [
                        ["Renewable", 0],
                        ["Natural Gas", 0],
                        ["Coal", 0],
                        ["Nuclear", 0],
                    ],
                },
            },
            "mapping": {
                "x": {"field": "source", "type": "category"},
                "series": [{"name": "Share", "y_field": "share", "axis": "left"}],
            },
            "options": {
                "show_legend": True,
                "show_values": True,
            },
        },
        "fields_json": {
            "caption": "[[AUTO:FIGURE_LABEL]] — Energy mix for [[ASK:PERIOD]]",
            "insight_text": "Breakdown of energy sources in the overall energy mix.",
            "unit": "%",
        },
    },
}

# --- Table Templates (New) ---

TABLE_SASB_INDEX = {
    "template_id": str(uuid4()),
    "scope": "block",
    "block_type": "table",
    "name": "SASB Index",
    "description": "SASB Content Index reference table",
    "tags": ["table", "sasb", "index", "standards", "disclosure"],
    "is_system": True,
    "template_json": {
        "variant": "default",
        "data_json": {
            "schema_version": 1,
            "columns": [
                {"key": "topic", "header": "Topic", "type": "text", "width": 200},
                {"key": "metric", "header": "Metric", "type": "text", "width": 250},
                {"key": "code", "header": "Code", "type": "text", "width": 100},
                {"key": "location", "header": "Location", "type": "text", "width": 200},
            ],
            "rows": [
                {"topic": "[[ASK:TOPIC]]", "metric": "[[ASK:METRIC]]", "code": "[[ASK:CODE]]", "location": "[[REF:SECTION]]"},
            ],
        },
        "fields_json": {
            "title": "SASB Index",
            "caption": "[[AUTO:TABLE_LABEL]] — SASB Content Index",
            "notes": "See SASB Standards for detailed metric definitions",
        },
    },
}

TABLE_SDG_ALIGNMENT = {
    "template_id": str(uuid4()),
    "scope": "block",
    "block_type": "table",
    "name": "SDG Alignment",
    "description": "UN Sustainable Development Goals alignment table",
    "tags": ["table", "sdg", "un", "sustainability", "goals"],
    "is_system": True,
    "template_json": {
        "variant": "default",
        "data_json": {
            "schema_version": 1,
            "columns": [
                {"key": "sdg", "header": "SDG", "type": "text", "width": 80},
                {"key": "goal", "header": "Goal", "type": "text", "width": 250},
                {"key": "contribution", "header": "Our Contribution", "type": "text", "width": 300},
                {"key": "target", "header": "Targets", "type": "text", "width": 150},
            ],
            "rows": [
                {"sdg": "[[ASK:SDG_NUMBER]]", "goal": "[[ASK:SDG_TITLE]]", "contribution": "[[ASK:CONTRIBUTION]]", "target": "[[OPT:TARGETS]]"},
            ],
        },
        "fields_json": {
            "title": "SDG Alignment",
            "caption": "[[AUTO:TABLE_LABEL]] — Contribution to UN Sustainable Development Goals",
            "notes": "",
        },
    },
}

TABLE_BOARD_COMPOSITION = {
    "template_id": str(uuid4()),
    "scope": "block",
    "block_type": "table",
    "name": "Board Composition",
    "description": "Corporate governance board composition table",
    "tags": ["table", "governance", "board", "diversity"],
    "is_system": True,
    "template_json": {
        "variant": "default",
        "data_json": {
            "schema_version": 1,
            "columns": [
                {"key": "metric", "header": "Metric", "type": "text", "width": 200},
                {"key": "value", "header": "Value", "type": "text", "width": 150},
                {"key": "percentage", "header": "%", "type": "number", "width": 80},
            ],
            "rows": [
                {"metric": "Total Board Members", "value": "[[ASK:TOTAL_MEMBERS]]", "percentage": None},
                {"metric": "Independent Directors", "value": "[[ASK:INDEPENDENT]]", "percentage": None},
                {"metric": "Women on Board", "value": "[[ASK:WOMEN]]", "percentage": None},
                {"metric": "Average Tenure (years)", "value": "[[ASK:TENURE]]", "percentage": None},
            ],
        },
        "fields_json": {
            "title": "Board Composition",
            "caption": "[[AUTO:TABLE_LABEL]] — Board composition as of [[ASK:PERIOD]]",
            "notes": "",
        },
    },
}

# --- KPI Templates (New) ---

KPI_GOVERNANCE = {
    "template_id": str(uuid4()),
    "scope": "block",
    "block_type": "kpi_cards",
    "name": "Governance KPIs",
    "description": "Corporate governance key performance indicators",
    "tags": ["kpi", "governance", "compliance", "ethics"],
    "is_system": True,
    "template_json": {
        "variant": "default",
        "data_json": {
            "schema_version": 2,
            "items": [
                {"item_id": "board-independence", "value": 0, "unit": "%", "period": "[[ASK:PERIOD]]"},
                {"item_id": "board-diversity", "value": 0, "unit": "%", "period": "[[ASK:PERIOD]]"},
                {"item_id": "ethics-training", "value": 0, "unit": "%", "period": "[[ASK:PERIOD]]"},
                {"item_id": "compliance-issues", "value": 0, "unit": "", "period": "[[ASK:PERIOD]]"},
            ],
        },
        "fields_json": {
            "title": "Corporate governance",
            "template_id": "governance",
            "items": [
                {"label": "Independent directors"},
                {"label": "Women on the Board"},
                {"label": "Ethics training"},
                {"label": "Violations"},
            ],
        },
    },
}

KPI_COMMUNITY_INVESTMENT = {
    "template_id": str(uuid4()),
    "scope": "block",
    "block_type": "kpi_cards",
    "name": "Community Investment",
    "description": "Social investment and community engagement metrics",
    "tags": ["kpi", "social", "community", "investment"],
    "is_system": True,
    "template_json": {
        "variant": "default",
        "data_json": {
            "schema_version": 2,
            "items": [
                {"item_id": "investment", "value": 0, "unit": "[[ASK:CURRENCY]]", "period": "[[ASK:PERIOD]]"},
                {"item_id": "beneficiaries", "value": 0, "unit": "people", "period": "[[ASK:PERIOD]]"},
                {"item_id": "projects", "value": 0, "unit": "", "period": "[[ASK:PERIOD]]"},
                {"item_id": "volunteers", "value": 0, "unit": "hours", "period": "[[ASK:PERIOD]]"},
            ],
        },
        "fields_json": {
            "title": "Social investment",
            "template_id": "community_investment",
            "items": [
                {"label": "Investment"},
                {"label": "Beneficiaries"},
                {"label": "Projects"},
                {"label": "Volunteering"},
            ],
        },
    },
}

KPI_DIVERSITY_INCLUSION = {
    "template_id": str(uuid4()),
    "scope": "block",
    "block_type": "kpi_cards",
    "name": "Diversity & Inclusion",
    "description": "Workforce diversity and inclusion metrics",
    "tags": ["kpi", "diversity", "inclusion", "people", "dei"],
    "is_system": True,
    "template_json": {
        "variant": "default",
        "data_json": {
            "schema_version": 2,
            "items": [
                {"item_id": "women-workforce", "value": 0, "unit": "%", "period": "[[ASK:PERIOD]]"},
                {"item_id": "women-management", "value": 0, "unit": "%", "period": "[[ASK:PERIOD]]"},
                {"item_id": "women-board", "value": 0, "unit": "%", "period": "[[ASK:PERIOD]]"},
                {"item_id": "pay-equity", "value": 0, "unit": "%", "period": "[[ASK:PERIOD]]"},
            ],
        },
        "fields_json": {
            "title": "Diversity and inclusion",
            "template_id": "diversity_inclusion",
            "items": [
                {"label": "Women in workforce"},
                {"label": "Women in management"},
                {"label": "Women on the Board"},
                {"label": "Pay equity"},
            ],
        },
    },
}

# ============================================================
# All Templates
# ============================================================

ALL_TEMPLATES = [
    # KPI (Original)
    KPI_COMPANY_IN_NUMBERS,
    KPI_CLIMATE,
    KPI_HSE,
    KPI_PEOPLE,
    # Charts (Original)
    CHART_TREND_3_YEAR,
    CHART_YOY_BAR,
    CHART_STACKED,
    CHART_PIE,
    # Tables (Original)
    TABLE_ESG_METRICS,
    TABLE_GRI_INDEX,
    TABLE_TARGETS,
    # Timelines (Original)
    TIMELINE_KEY_EVENTS,
    TIMELINE_ROADMAP,
    # NEW: Quotes
    CEO_MESSAGE,
    # NEW: Text
    CALLOUT_BOX,
    # NEW: Downloads
    DOWNLOADS_SECTION,
    # NEW: Charts
    CHART_EMISSIONS_BY_SCOPE,
    CHART_WATER_USAGE,
    CHART_ENERGY_MIX,
    # NEW: Tables
    TABLE_SASB_INDEX,
    TABLE_SDG_ALIGNMENT,
    TABLE_BOARD_COMPOSITION,
    # NEW: KPI
    KPI_GOVERNANCE,
    KPI_COMMUNITY_INVESTMENT,
    KPI_DIVERSITY_INCLUSION,
]


async def seed_templates(session) -> None:
    """Seed built-in templates into the database.

    This is intended to be safe to run multiple times:
    - Insert missing system templates
    - Update existing system templates in place (by name)
    """
    from sqlalchemy import select
    from app.domain.models import Template

    changed = 0
    for template_data in ALL_TEMPLATES:
        # Check if template with same name already exists
        query = select(Template).where(
            Template.name == template_data["name"],
            Template.is_system == True,
        )
        result = await session.execute(query)
        existing = result.scalar_one_or_none()

        if existing:
            needs_update = (
                existing.scope != template_data["scope"]
                or existing.block_type != template_data["block_type"]
                or existing.description != template_data["description"]
                or (existing.tags or []) != (template_data["tags"] or [])
                or (existing.template_json or {}) != (template_data["template_json"] or {})
                or existing.is_active != True
            )
            if needs_update:
                existing.scope = template_data["scope"]
                existing.block_type = template_data["block_type"]
                existing.description = template_data["description"]
                existing.tags = template_data["tags"]
                existing.template_json = template_data["template_json"]
                existing.is_active = True
                changed += 1
            continue

        template = Template(
            scope=template_data["scope"],
            block_type=template_data["block_type"],
            name=template_data["name"],
            description=template_data["description"],
            tags=template_data["tags"],
            template_json=template_data["template_json"],
            is_system=template_data["is_system"],
        )
        session.add(template)
        changed += 1

    await session.flush()
    return changed


if __name__ == "__main__":
    import asyncio
    from app.infra.database import async_session_factory

    async def main():
        async with async_session_factory() as session:
            changed = await seed_templates(session)
            await session.commit()
            print(f"✅ Seeded/updated {changed} system templates (total available: {len(ALL_TEMPLATES)})")
            print(f"   13 original + 12 new with ASK/AUTO/OPT placeholders = {len(ALL_TEMPLATES)} templates")

    asyncio.run(main())
