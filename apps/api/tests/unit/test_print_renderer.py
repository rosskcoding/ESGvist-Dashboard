"""Unit tests for print report rendering."""

import pytest
from uuid import uuid4
from unittest.mock import MagicMock, patch

from app.domain.models.enums import BlockType, Locale, BlockVariant
from app.services.renderer import Renderer, BlockCounters


class TestRenderPrintReport:
    """Tests for render_print_report method."""

    @pytest.fixture
    def renderer(self):
        """Create renderer instance."""
        return Renderer()

    @pytest.fixture
    def mock_report(self):
        """Create mock report."""
        report = MagicMock()
        report.report_id = uuid4()
        report.title = "Test Report"
        report.year = 2024
        report.description = "Test description"
        report.company = MagicMock()
        report.company.name = "Test Company"
        return report

    @pytest.fixture
    def mock_section(self):
        """Create mock section."""
        section = MagicMock()
        section.section_id = uuid4()
        section.order_index = 0

        # Mock i18n
        i18n = MagicMock()
        i18n.title = "Section 1"
        i18n.summary = "Section summary"
        i18n.slug = "section-1"
        section.get_i18n = MagicMock(return_value=i18n)

        return section

    @pytest.fixture
    def mock_block(self):
        """Create mock block."""
        block = MagicMock()
        block.block_id = uuid4()
        block.type = BlockType.TEXT
        block.variant = BlockVariant.DEFAULT
        block.data_json = {}

        # Mock i18n
        i18n = MagicMock()
        i18n.fields_json = {"body_html": "<p>Test content</p>"}
        block.get_i18n = MagicMock(return_value=i18n)

        return block

    def test_render_print_report_basic(self, renderer, mock_report, mock_section, mock_block):
        """Test basic print report rendering."""
        sections = [mock_section]
        blocks_by_section = {str(mock_section.section_id): [mock_block]}

        html = renderer.render_print_report(
            report=mock_report,
            sections=sections,
            blocks_by_section=blocks_by_section,
            locale="en",
            theme=None,
            assets_base_url="/assets",
        )

        # Check basic structure
        assert "<!DOCTYPE html>" in html
        assert 'lang="en"' in html
        assert 'data-render-mode="print"' in html

        # Check title page
        assert "Test Report" in html
        assert "2024" in html
        assert "Test Company" in html

        # Check section
        assert "Section 1" in html
        assert "Test content" in html

    def test_render_print_report_includes_toc(self, renderer, mock_report, mock_section, mock_block):
        """Test TOC generation in print report."""
        sections = [mock_section]
        blocks_by_section = {str(mock_section.section_id): [mock_block]}

        html = renderer.render_print_report(
            report=mock_report,
            sections=sections,
            blocks_by_section=blocks_by_section,
            locale="en",
            theme=None,
            include_toc=True,
        )

        # Check TOC
        assert "Contents" in html
        assert "Section 1" in html
        assert 'href="#section-0"' in html

    def test_render_print_report_english_locale(self, renderer, mock_report, mock_section, mock_block):
        """Test print report with English locale."""
        sections = [mock_section]
        blocks_by_section = {str(mock_section.section_id): [mock_block]}

        html = renderer.render_print_report(
            report=mock_report,
            sections=sections,
            blocks_by_section=blocks_by_section,
            locale="en",
            theme=None,
            include_toc=True,
        )

        assert 'lang="en"' in html
        assert "Contents" in html  # English TOC title
        assert "Generated:" in html  # English footer

    def test_render_print_report_kazakh_locale(self, renderer, mock_report, mock_section, mock_block):
        """Test print report with Kazakh locale."""
        sections = [mock_section]
        blocks_by_section = {str(mock_section.section_id): [mock_block]}

        html = renderer.render_print_report(
            report=mock_report,
            sections=sections,
            blocks_by_section=blocks_by_section,
            locale="kk",
            theme=None,
            include_toc=True,
        )

        assert 'lang="kk"' in html
        assert "Contents" in html
        assert "Generated:" in html

    def test_render_print_report_multiple_sections(self, renderer, mock_report):
        """Test print report with multiple sections."""
        sections = []
        blocks_by_section = {}

        for i in range(3):
            section = MagicMock()
            section.section_id = uuid4()
            section.order_index = i

            i18n = MagicMock()
            i18n.title = f"Section {i + 1}"
            i18n.summary = None
            section.get_i18n = MagicMock(return_value=i18n)

            sections.append(section)
            blocks_by_section[str(section.section_id)] = []

        html = renderer.render_print_report(
            report=mock_report,
            sections=sections,
            blocks_by_section=blocks_by_section,
            locale="en",
        )

        # Check all sections present
        assert "Section 1" in html
        assert "Section 2" in html
        assert "Section 3" in html

        # Check section anchors
        assert 'id="section-0"' in html
        assert 'id="section-1"' in html
        assert 'id="section-2"' in html

    def test_render_print_report_custom_generated_at(self, renderer, mock_report, mock_section, mock_block):
        """Test custom generated_at timestamp."""
        sections = [mock_section]
        blocks_by_section = {str(mock_section.section_id): [mock_block]}

        html = renderer.render_print_report(
            report=mock_report,
            sections=sections,
            blocks_by_section=blocks_by_section,
            locale="en",
            generated_at="2024-12-28 15:00",
        )

        assert "2024-12-28 15:00" in html

    def test_render_print_report_no_js(self, renderer, mock_report, mock_section, mock_block):
        """Verify print HTML doesn't include JavaScript."""
        sections = [mock_section]
        blocks_by_section = {str(mock_section.section_id): [mock_block]}

        html = renderer.render_print_report(
            report=mock_report,
            sections=sections,
            blocks_by_section=blocks_by_section,
            locale="en",
        )

        # Should not contain script tags or JS references
        assert "<script" not in html
        assert ".js" not in html

    def test_render_print_report_includes_print_css(self, renderer, mock_report, mock_section, mock_block):
        """Verify print.css is linked."""
        sections = [mock_section]
        blocks_by_section = {str(mock_section.section_id): [mock_block]}

        html = renderer.render_print_report(
            report=mock_report,
            sections=sections,
            blocks_by_section=blocks_by_section,
            locale="en",
            assets_base_url="/assets",
        )

        assert '/assets/css/print.css' in html


class TestBlockCounters:
    """Tests for BlockCounters class."""

    def test_counter_initialization(self):
        """Test counters start at 0."""
        counters = BlockCounters()
        assert counters.table == 0
        assert counters.figure == 0
        assert counters.box == 0

    def test_next_table_increments(self):
        """Test next_table increments counter."""
        counters = BlockCounters()
        assert counters.next_table() == 1
        assert counters.next_table() == 2
        assert counters.next_table() == 3

    def test_next_figure_increments(self):
        """Test next_figure increments counter."""
        counters = BlockCounters()
        assert counters.next_figure() == 1
        assert counters.next_figure() == 2

    def test_counters_independent(self):
        """Test different counter types are independent."""
        counters = BlockCounters()
        assert counters.next_table() == 1
        assert counters.next_figure() == 1
        assert counters.next_box() == 1
        assert counters.next_table() == 2
        assert counters.figure == 1
