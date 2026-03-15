"""
Sample ESG report fixtures for testing.

Realistic sample content for validating blocks, themes, and export.
Based on a typical annual ESG report.
"""

from uuid import UUID

# ============================================================================
# REPORT METADATA
# ============================================================================

SAMPLE_REPORT = {
    "report_id": UUID("550e8400-e29b-41d4-a716-446655440000"),
    "year": 2024,
    "title": "Annual Sustainability Report",
    "source_locale": "en",
    "default_locale": "en",
    "enabled_locales": ["en"],
    "release_locales": ["en"],
    "theme_slug": "corporate-blue",
}

# ============================================================================
# SECTIONS (TOC Structure)
# ============================================================================

SAMPLE_SECTIONS = [
    {
        "section_id": UUID("a1000000-0000-0000-0000-000000000001"),
        "order_index": 0,
        "i18n": {"en": {"title": "About Company", "slug": "about-company"}},
    },
    {
        "section_id": UUID("a1000000-0000-0000-0000-000000000002"),
        "order_index": 1,
        "i18n": {
            "en": {"title": "Key Performance Indicators", "slug": "key-performance-indicators"}
        },
    },
    {
        "section_id": UUID("a1000000-0000-0000-0000-000000000003"),
        "order_index": 2,
        "i18n": {
            "en": {
                "title": "Environmental Responsibility",
                "slug": "environmental-responsibility",
            }
        },
    },
    {
        "section_id": UUID("a1000000-0000-0000-0000-000000000004"),
        "order_index": 3,
        "i18n": {"en": {"title": "Social Policy", "slug": "social-policy"}},
    },
    {
        "section_id": UUID("a1000000-0000-0000-0000-000000000005"),
        "order_index": 4,
        "i18n": {"en": {"title": "Corporate Governance", "slug": "corporate-governance"}},
    },
]

# ============================================================================
# BLOCKS BY TYPE
# ============================================================================

# --- TEXT BLOCK ---
BLOCK_TEXT_ABOUT = {
    "block_id": UUID("b1000000-0000-0000-0000-000000000001"),
    "section_id": UUID("a1000000-0000-0000-0000-000000000001"),
    "type": "text",
    "variant": "default",
    "order_index": 0,
    "data_json": {},  # Text blocks have no non-localized data
    "i18n": {
        "en": {
            "status": "ready",
            "fields_json": {
                "body_html": """
<p><strong>KazEnergo JSC</strong> is a leading energy company in Kazakhstan,
specializing in the production, transmission, and distribution of electricity.</p>

<p>Founded in 1995, the company now provides electricity to more than
<strong>5 million</strong> consumers across 8 regions of the country.</p>

<h3>Our Mission</h3>
<p>Providing reliable and sustainable energy supply for economic development
and improving the quality of life for the people of Kazakhstan.</p>

<h3>Strategic Priorities</h3>
<ul>
    <li>Modernization of energy infrastructure</li>
    <li>Development of renewable energy sources</li>
    <li>Carbon footprint reduction</li>
    <li>Process digitalization</li>
</ul>
""",
            },
        }
    },
}

# --- KPI CARDS BLOCK ---
BLOCK_KPI_CARDS = {
    "block_id": UUID("b1000000-0000-0000-0000-000000000002"),
    "section_id": UUID("a1000000-0000-0000-0000-000000000002"),
    "type": "kpi_cards",
    "variant": "emphasized",
    "order_index": 0,
    "data_json": {
        "columns": 4,
        "items": [
            {"icon": "⚡", "color": "#3b82f6"},
            {"icon": "👥", "color": "#22c55e"},
            {"icon": "🌱", "color": "#10b981"},
            {"icon": "💰", "color": "#f59e0b"},
        ],
    },
    "i18n": {
        "en": {
            "status": "ready",
            "fields_json": {
                "items": [
                    {"label": "Electricity Generation", "value": "42.5 TWh", "delta": "+8.2%"},
                    {"label": "Headcount", "value": "12,450", "delta": "+3.1%"},
                    {"label": "Renewable Share", "value": "18.7%", "delta": "+2.4 p.p."},
                    {"label": "Revenue", "value": "KZT 845 bn", "delta": "+12.5%"},
                ],
            },
        }
    },
}

# --- TABLE BLOCK (Builder mode) ---
BLOCK_TABLE_EMISSIONS = {
    "block_id": UUID("b1000000-0000-0000-0000-000000000003"),
    "section_id": UUID("a1000000-0000-0000-0000-000000000003"),
    "type": "table",
    "variant": "default",
    "order_index": 0,
    "data_json": {
        "mode": "builder",
        "columns": [
            {"key": "indicator", "width": 200},
            {"key": "unit", "width": 100},
            {"key": "y2022", "width": 100, "align": "right"},
            {"key": "y2023", "width": 100, "align": "right"},
            {"key": "y2024", "width": 100, "align": "right"},
            {"key": "target2025", "width": 100, "align": "right"},
        ],
        "rows": 5,
        "has_header": True,
        "has_footer": False,
    },
    "i18n": {
        "en": {
            "status": "ready",
            "fields_json": {
                "caption": "Table 3.1. Greenhouse Gas Emissions Dynamics",
                "header_row": ["Indicator", "Unit", "2022", "2023", "2024", "Target 2025"],
                "data_rows": [
                    ["CO2 Emissions (Scope 1)", "kt", "1,245", "1,180", "1,098", "1,000"],
                    ["CO2 Emissions (Scope 2)", "kt", "328", "310", "295", "280"],
                    ["Emission Intensity", "kg CO2/MWh", "412", "398", "385", "370"],
                    ["Methane Emissions", "kt CO2-eq.", "45", "42", "38", "35"],
                    ["Total GHG", "kt CO2-eq.", "1,618", "1,532", "1,431", "1,315"],
                ],
                "footnotes": "Data verified by independent auditor (Bureau Veritas)",
            },
        }
    },
}

# --- CHART BLOCK ---
BLOCK_CHART_ENERGY_MIX = {
    "block_id": UUID("b1000000-0000-0000-0000-000000000004"),
    "section_id": UUID("a1000000-0000-0000-0000-000000000003"),
    "type": "chart",
    "variant": "default",
    "order_index": 1,
    "data_json": {
        "chart_type": "pie",
        "series": [
            {"key": "coal", "value": 52.3, "color": "#64748b"},
            {"key": "gas", "value": 29.0, "color": "#3b82f6"},
            {"key": "hydro", "value": 10.5, "color": "#22c55e"},
            {"key": "wind", "value": 5.2, "color": "#06b6d4"},
            {"key": "solar", "value": 3.0, "color": "#f59e0b"},
        ],
    },
    "i18n": {
        "en": {
            "status": "ready",
            "fields_json": {
                "title": "Generation Mix by Energy Source, 2024",
                "labels": {
                    "coal": "Coal",
                    "gas": "Natural Gas",
                    "hydro": "Hydropower",
                    "wind": "Wind Power",
                    "solar": "Solar Energy",
                },
                "insight_text": "The share of renewable energy sources reached 18.7%, which is 2.4 percentage points higher than in 2023.",
            },
        }
    },
}

# --- IMAGE BLOCK ---
BLOCK_IMAGE_SOLAR = {
    "block_id": UUID("b1000000-0000-0000-0000-000000000005"),
    "section_id": UUID("a1000000-0000-0000-0000-000000000003"),
    "type": "image",
    "variant": "full_width",
    "order_index": 2,
    "data_json": {
        "asset_id": "img-solar-plant-001",  # Reference to asset
        "aspect_ratio": "16:9",
    },
    "i18n": {
        "en": {
            "status": "ready",
            "fields_json": {
                "alt_text": "100 MW solar power plant in Turkestan region",
                "caption": "Saryarka Solar power plant (100 MW), commissioned in 2024",
            },
        }
    },
}

# --- QUOTE BLOCK ---
BLOCK_QUOTE_CEO = {
    "block_id": UUID("b1000000-0000-0000-0000-000000000006"),
    "section_id": UUID("a1000000-0000-0000-0000-000000000001"),
    "type": "quote",
    "variant": "emphasized",
    "order_index": 1,
    "data_json": {
        "author_photo_asset_id": "img-ceo-portrait-001",
    },
    "i18n": {
        "en": {
            "status": "ready",
            "fields_json": {
                "quote_text": "Sustainable development is not just a trend, but a strategic imperative for the energy sector. We invest in green technologies because we believe the future of energy lies in clean sources.",
                "author_name": "Yerlan Satybaldiyev",
                "author_title": "Chairman of the Board, KazEnergo JSC",
            },
        }
    },
}

# --- ACCORDION BLOCK (FAQ) ---
BLOCK_ACCORDION_ESG = {
    "block_id": UUID("b1000000-0000-0000-0000-000000000007"),
    "section_id": UUID("a1000000-0000-0000-0000-000000000005"),
    "type": "accordion",
    "variant": "default",
    "order_index": 0,
    "data_json": {
        "allow_multiple_open": False,
        "items_count": 4,
    },
    "i18n": {
        "en": {
            "status": "ready",
            "fields_json": {
                "items": [
                    {
                        "title": "What is ESG reporting?",
                        "content_html": "<p><strong>ESG</strong> (Environmental, Social, Governance) is a framework for evaluating a company across three key dimensions: environmental, social, and governance. ESG reporting enables investors and stakeholders to assess business sustainability in the long term.</p>",
                    },
                    {
                        "title": "What standards are used?",
                        "content_html": "<p>The company prepares reports in accordance with international standards:</p><ul><li>GRI Standards (Global Reporting Initiative)</li><li>SASB (Sustainability Accounting Standards Board)</li><li>TCFD (Task Force on Climate-related Financial Disclosures)</li></ul>",
                    },
                    {
                        "title": "How is information verified?",
                        "content_html": "<p>Key ESG metrics undergo independent verification by Bureau Veritas. The verification certificate is available in the report appendix.</p>",
                    },
                    {
                        "title": "Where to find historical data?",
                        "content_html": "<p>Archive of ESG reports for previous years is available on the <a href='/reports/archive'>archive page</a>. Data is available in PDF and Excel formats.</p>",
                    },
                ],
            },
        }
    },
}

# --- TIMELINE BLOCK ---
BLOCK_TIMELINE_MILESTONES = {
    "block_id": UUID("b1000000-0000-0000-0000-000000000008"),
    "section_id": UUID("a1000000-0000-0000-0000-000000000001"),
    "type": "timeline",
    "variant": "default",
    "order_index": 2,
    "data_json": {
        "orientation": "vertical",
        "items_count": 5,
    },
    "i18n": {
        "en": {
            "status": "ready",
            "fields_json": {
                "title": "Key Development Milestones",
                "items": [
                    {"year": "1995", "event": "Company founded"},
                    {"year": "2005", "event": "Entry into international capital markets"},
                    {"year": "2015", "event": "First wind power plant launched"},
                    {"year": "2020", "event": "Carbon Neutrality Strategy adopted"},
                    {"year": "2024", "event": "Renewable share reached 18.7%"},
                ],
            },
        }
    },
}

# --- DOWNLOADS BLOCK ---
BLOCK_DOWNLOADS = {
    "block_id": UUID("b1000000-0000-0000-0000-000000000009"),
    "section_id": UUID("a1000000-0000-0000-0000-000000000005"),
    "type": "downloads",
    "variant": "default",
    "order_index": 1,
    "data_json": {
        "items": [
            {"asset_id": "file-annual-report-pdf", "file_type": "pdf", "size_bytes": 15728640},
            {"asset_id": "file-esg-data-xlsx", "file_type": "xlsx", "size_bytes": 524288},
            {"asset_id": "file-gri-index-pdf", "file_type": "pdf", "size_bytes": 2097152},
        ],
    },
    "i18n": {
        "en": {
            "status": "ready",
            "fields_json": {
                "title": "Download Materials",
                "items": [
                    {"label": "Annual Report 2024 (PDF)", "description": "Full report version"},
                    {"label": "ESG Data (Excel)", "description": "Key metrics for 5 years"},
                    {"label": "GRI Content Index (PDF)", "description": "GRI Standards compliance index"},
                ],
            },
        }
    },
}

# ============================================================================
# ALL BLOCKS COLLECTION
# ============================================================================

ALL_SAMPLE_BLOCKS = [
    BLOCK_TEXT_ABOUT,
    BLOCK_QUOTE_CEO,
    BLOCK_TIMELINE_MILESTONES,
    BLOCK_KPI_CARDS,
    BLOCK_TABLE_EMISSIONS,
    BLOCK_CHART_ENERGY_MIX,
    BLOCK_IMAGE_SOLAR,
    BLOCK_ACCORDION_ESG,
    BLOCK_DOWNLOADS,
]

# ============================================================================
# GLOSSARY TERMS
# ============================================================================

SAMPLE_GLOSSARY = [
    {
        "term_id": UUID("c1000000-0000-0000-0000-000000000001"),
        "en": "renewable energy sources",
        "strictness": "strict",
        "notes": "Abbreviation: RES",
    },
    {
        "term_id": UUID("c1000000-0000-0000-0000-000000000002"),
        "en": "carbon footprint",
        "strictness": "strict",
    },
    {
        "term_id": UUID("c1000000-0000-0000-0000-000000000003"),
        "en": "greenhouse gases",
        "strictness": "strict",
        "notes": "Abbreviation: GHG",
    },
    {
        "term_id": UUID("c1000000-0000-0000-0000-000000000004"),
        "en": "sustainable development",
        "strictness": "preferred",
    },
    {
        "term_id": UUID("c1000000-0000-0000-0000-000000000005"),
        "en": "KazEnergo JSC",
        "strictness": "do_not_translate",
        "notes": "Company name should not be translated",
    },
    {
        "term_id": UUID("c1000000-0000-0000-0000-000000000006"),
        "en": "Chairman of the Board",
        "strictness": "strict",
    },
]

# ============================================================================
# USERS
# ============================================================================

SAMPLE_USERS = [
    {
        "user_id": UUID("d1000000-0000-0000-0000-000000000001"),
        "email": "admin@kazenergo.kz",
        "full_name": "System Administrator",
        "locale_scopes": None,  # Global access
        "is_superuser": True,
    },
    {
        "user_id": UUID("d1000000-0000-0000-0000-000000000002"),
        "email": "editor@kazenergo.kz",
        "full_name": "Editor-in-chief",
        "locale_scopes": ["en"],
    },
    {
        "user_id": UUID("d1000000-0000-0000-0000-000000000003"),
        "email": "content_editor@kazenergo.kz",
        "full_name": "Content editor",
        "locale_scopes": ["en"],
    },
    {
        "user_id": UUID("d1000000-0000-0000-0000-000000000004"),
        "email": "sme@kazenergo.kz",
        "full_name": "Section SME",
        "locale_scopes": None,  # All locales
    },
]

