"""
Test Fixtures for ESG Report Creator

Contains sample data for testing:
- sample_report: Full ESG report with all block types
- sample_theme: Theme definitions with CSS variables
"""

from .sample_report import (
    ALL_SAMPLE_BLOCKS,
    BLOCK_ACCORDION_ESG,
    BLOCK_CHART_ENERGY_MIX,
    BLOCK_DOWNLOADS,
    BLOCK_IMAGE_SOLAR,
    BLOCK_KPI_CARDS,
    BLOCK_QUOTE_CEO,
    BLOCK_TABLE_EMISSIONS,
    # Individual blocks
    BLOCK_TEXT_ABOUT,
    BLOCK_TIMELINE_MILESTONES,
    SAMPLE_GLOSSARY,
    SAMPLE_REPORT,
    SAMPLE_SECTIONS,
    SAMPLE_USERS,
)
from .sample_theme import (
    ALL_THEMES,
    DEFAULT_THEME_SLUG,
    THEME_CORPORATE_BLUE,
    THEME_DARK_MODE,
    THEME_GREEN_SUSTAINABILITY,
    generate_css_variables,
)

__all__ = [
    # Report
    "SAMPLE_REPORT",
    "SAMPLE_SECTIONS",
    "ALL_SAMPLE_BLOCKS",
    "SAMPLE_GLOSSARY",
    "SAMPLE_USERS",
    # Blocks
    "BLOCK_TEXT_ABOUT",
    "BLOCK_KPI_CARDS",
    "BLOCK_TABLE_EMISSIONS",
    "BLOCK_CHART_ENERGY_MIX",
    "BLOCK_IMAGE_SOLAR",
    "BLOCK_QUOTE_CEO",
    "BLOCK_ACCORDION_ESG",
    "BLOCK_TIMELINE_MILESTONES",
    "BLOCK_DOWNLOADS",
    # Themes
    "ALL_THEMES",
    "THEME_CORPORATE_BLUE",
    "THEME_GREEN_SUSTAINABILITY",
    "THEME_DARK_MODE",
    "DEFAULT_THEME_SLUG",
    "generate_css_variables",
]






