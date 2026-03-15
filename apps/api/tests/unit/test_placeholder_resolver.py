"""
Unit tests for placeholder resolver (app.services.placeholder_resolver).

Tests placeholder resolution for templates including:
- AUTO placeholders (auto-numbering)
- ASK placeholders (user-provided values)
- OPT placeholders (optional values)
- REF placeholders (references)
- Legacy placeholders (backwards compatibility)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.services.placeholder_resolver import (
    resolve_placeholders,
    ResolveContext,
    extract_placeholders,
    has_unresolved_placeholders,
    _resolve_string,
    _resolve_auto,
)


class TestResolveString:
    """Test individual string resolution."""

    def test_no_placeholders(self):
        """String without placeholders returns unchanged."""
        context = MagicMock(table_count=0, figure_count=0, box_count=0, locale="en")
        result = _resolve_string("Hello world", context, {})
        assert result == "Hello world"

    def test_auto_table_label(self):
        """AUTO:TABLE_LABEL generates table number."""
        context = MagicMock(table_count=2, figure_count=0, box_count=0, locale="en")
        result = _resolve_string("[[AUTO:TABLE_LABEL]] — Data", context, {})
        assert result == "Table 3 — Data"
        assert context.table_count == 3

    def test_auto_figure_label(self):
        """AUTO:FIGURE_LABEL generates figure number."""
        context = MagicMock(table_count=0, figure_count=4, box_count=0, locale="en")
        result = _resolve_string("[[AUTO:FIGURE_LABEL]] — Chart", context, {})
        assert result == "Figure 5 — Chart"
        assert context.figure_count == 5

    def test_auto_box_label(self):
        """AUTO:BOX_LABEL generates box number."""
        context = MagicMock(table_count=0, figure_count=0, box_count=0, locale="en")
        result = _resolve_string("[[AUTO:BOX_LABEL]] — Note", context, {})
        assert result == "Box 1 — Note"
        assert context.box_count == 1

    def test_auto_current_year(self):
        """AUTO:CURRENT_YEAR returns current year."""
        context = MagicMock(table_count=0, figure_count=0, box_count=0, locale="en")
        result = _resolve_string("© [[AUTO:CURRENT_YEAR]]", context, {})
        assert "© 202" in result  # Will be 2024, 2025, etc.

    def test_ask_placeholder_with_override(self):
        """ASK placeholder resolved from overrides."""
        context = MagicMock(table_count=0, figure_count=0, box_count=0, locale="en")
        overrides = {"PERIOD": "2024"}
        result = _resolve_string("Report for [[ASK:PERIOD]]", context, overrides)
        assert result == "Report for 2024"

    def test_ask_placeholder_without_override(self):
        """ASK placeholder returns empty string if not provided."""
        context = MagicMock(table_count=0, figure_count=0, box_count=0, locale="en")
        result = _resolve_string("Report for [[ASK:PERIOD]]", context, {})
        assert result == "Report for "

    def test_opt_placeholder(self):
        """OPT placeholder works like ASK."""
        context = MagicMock(table_count=0, figure_count=0, box_count=0, locale="en")
        overrides = {"SOURCE": "Internal data"}
        result = _resolve_string("Source: [[OPT:SOURCE]]", context, overrides)
        assert result == "Source: Internal data"

    def test_ref_placeholder_with_override(self):
        """REF placeholder resolved from overrides."""
        context = MagicMock(table_count=0, figure_count=0, box_count=0, locale="en")
        overrides = {"SECTION": "Section 3.2"}
        result = _resolve_string("See [[REF:SECTION]]", context, overrides)
        assert result == "See Section 3.2"

    def test_ref_placeholder_without_override(self):
        """REF placeholder returns reference text if not provided."""
        context = MagicMock(table_count=0, figure_count=0, box_count=0, locale="en")
        result = _resolve_string("See [[REF:SECTION]]", context, {})
        assert result == "See [see SECTION]"

    def test_legacy_metric_name(self):
        """Legacy [[METRIC_NAME]] treated as ASK."""
        context = MagicMock(table_count=0, figure_count=0, box_count=0, locale="en")
        overrides = {"METRIC_NAME": "Revenue"}
        result = _resolve_string("[[METRIC_NAME]]", context, overrides)
        assert result == "Revenue"

    def test_legacy_section(self):
        """Legacy [[SECTION]] treated as REF."""
        context = MagicMock(table_count=0, figure_count=0, box_count=0, locale="en")
        result = _resolve_string("[[SECTION]]", context, {})
        assert result == "[see SECTION]"

    def test_multiple_placeholders(self):
        """Multiple placeholders in one string."""
        context = MagicMock(table_count=0, figure_count=0, box_count=0, locale="en")
        overrides = {"PERIOD": "2024"}
        text = "[[AUTO:TABLE_LABEL]] — Data for [[ASK:PERIOD]]"
        result = _resolve_string(text, context, overrides)
        assert result == "Table 1 — Data for 2024"


class TestResolveAuto:
    """Test AUTO placeholder resolution."""

    def test_unknown_auto_key(self):
        """Unknown AUTO key returns original placeholder."""
        context = MagicMock(table_count=0, figure_count=0, box_count=0, locale="en")
        result = _resolve_auto("UNKNOWN_KEY", context)
        assert result == "[[AUTO:UNKNOWN_KEY]]"

    def test_source_locale(self):
        """AUTO:SOURCE_LOCALE returns locale."""
        context = MagicMock(table_count=0, figure_count=0, box_count=0, locale="en")
        result = _resolve_auto("SOURCE_LOCALE", context)
        assert result == "en"


class TestExtractPlaceholders:
    """Test placeholder extraction."""

    def test_extract_from_flat_dict(self):
        """Extract placeholders from flat dict."""
        content = {
            "caption": "[[AUTO:TABLE_LABEL]] — ESG Data",
            "title": "Report [[ASK:PERIOD]]",
        }
        result = extract_placeholders(content)

        assert "TABLE_LABEL" in result["AUTO"]
        assert "PERIOD" in result["ASK"]

    def test_extract_from_nested_dict(self):
        """Extract placeholders from nested dict."""
        content = {
            "data_json": {
                "rows": [{"metric": "[[METRIC_NAME]]"}],
            },
            "fields_json": {
                "caption": "[[AUTO:FIGURE_LABEL]]",
            },
        }
        result = extract_placeholders(content)

        # METRIC_NAME is legacy, should be mapped to ASK
        assert "FIGURE_LABEL" in result["AUTO"]

    def test_extract_from_list(self):
        """Extract placeholders from list."""
        content = {
            "items": [
                {"label": "[[ASK:KPI_1]]"},
                {"label": "[[ASK:KPI_2]]"},
            ],
        }
        result = extract_placeholders(content)

        assert "KPI_1" in result["ASK"]
        assert "KPI_2" in result["ASK"]


class TestHasUnresolvedPlaceholders:
    """Test unresolved placeholder detection."""

    def test_no_placeholders(self):
        """Content without placeholders returns False."""
        content = {"caption": "Table 1", "data": [1, 2, 3]}
        assert has_unresolved_placeholders(content) is False

    def test_with_placeholders(self):
        """Content with placeholders returns True."""
        content = {"caption": "[[AUTO:TABLE_LABEL]]"}
        assert has_unresolved_placeholders(content) is True

    def test_nested_placeholders(self):
        """Nested placeholders detected."""
        content = {
            "outer": {
                "inner": {
                    "value": "[[ASK:VALUE]]",
                },
            },
        }
        assert has_unresolved_placeholders(content) is True


class TestResolveContext:
    """Test ResolveContext dataclass."""

    def test_context_creation(self):
        """Context can be created with required fields."""
        context = ResolveContext(
            report_id=uuid4(),
            section_id=uuid4(),
            session=MagicMock(),
            locale="en",
        )

        assert context.table_count == 0
        assert context.figure_count == 0
        assert context.box_count == 0
        assert context._counts_loaded is False


class TestResolvePlaceholdersIntegration:
    """Integration tests for full resolve_placeholders function."""

    @pytest.mark.asyncio
    async def test_resolve_template_content(self):
        """Full template content resolution."""
        # Mock session
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 2  # 2 existing tables
        mock_session.execute.return_value = mock_result

        context = ResolveContext(
            report_id=uuid4(),
            section_id=uuid4(),
            session=mock_session,
            locale="en",
        )

        content = {
            "variant": "default",
            "data_json": {
                "rows": [
                    {"metric": "[[METRIC_NAME]]", "value": None},
                ],
            },
            "fields_json": {
                "caption": "[[AUTO:TABLE_LABEL]] — ESG metrics",
                "title": "Data for [[ASK:PERIOD]]",
            },
        }

        overrides = {
            "PERIOD": "2024",
            "METRIC_NAME": "CO2 emissions",
        }

        result = await resolve_placeholders(content, context, overrides)

        # Check fields_json resolved
        assert "Table 3" in result["fields_json"]["caption"]
        assert "2024" in result["fields_json"]["title"]

        # Check data_json resolved
        assert result["data_json"]["rows"][0]["metric"] == "CO2 emissions"

    @pytest.mark.asyncio
    async def test_resolve_without_overrides(self):
        """Resolution without overrides clears ASK placeholders."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_session.execute.return_value = mock_result

        context = ResolveContext(
            report_id=uuid4(),
            section_id=uuid4(),
            session=mock_session,
            locale="en",
        )

        content = {
            "fields_json": {
                "caption": "[[AUTO:TABLE_LABEL]] — [[ASK:TITLE]]",
            },
        }

        result = await resolve_placeholders(content, context, None)

        # AUTO resolved, ASK becomes empty
        assert result["fields_json"]["caption"] == "Table 1 — "



