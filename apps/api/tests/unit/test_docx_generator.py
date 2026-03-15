"""Unit tests for DOCX generator service."""

import io
import sys
import types
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.domain.models.enums import BlockType, Locale


class TestBlockRenderers:
    """Tests for individual block renderers."""

    @pytest.fixture
    def mock_doc(self):
        """Create mock Document."""
        doc = MagicMock()
        doc.add_paragraph = MagicMock(return_value=MagicMock())
        doc.add_heading = MagicMock(return_value=MagicMock())
        doc.add_table = MagicMock(return_value=MagicMock())
        doc.add_picture = MagicMock()
        return doc

    @pytest.fixture
    def mock_session(self):
        """Create mock session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_render_text_simple(self, mock_doc, mock_session):
        """Test rendering simple text block."""
        from app.services.docx_generator import _render_text

        block = MagicMock()
        fields = {"body_html": "<p>Hello World</p>"}

        await _render_text(mock_doc, block, fields, {}, "ru", mock_session)

        mock_doc.add_paragraph.assert_called()

    @pytest.mark.asyncio
    async def test_render_text_with_headings(self, mock_doc, mock_session):
        """Test rendering text with headings."""
        from app.services.docx_generator import _render_text

        block = MagicMock()
        fields = {"body_html": "<h3>Title</h3><p>Content</p>"}

        await _render_text(mock_doc, block, fields, {}, "ru", mock_session)

        mock_doc.add_heading.assert_called()
        mock_doc.add_paragraph.assert_called()

    @pytest.mark.asyncio
    async def test_render_text_with_lists(self, mock_doc, mock_session):
        """Test rendering text with lists."""
        from app.services.docx_generator import _render_text

        block = MagicMock()
        fields = {"body_html": "<ul><li>Item 1</li><li>Item 2</li></ul>"}

        await _render_text(mock_doc, block, fields, {}, "ru", mock_session)

        # Should add paragraphs with list style
        assert mock_doc.add_paragraph.call_count >= 2

    @pytest.mark.asyncio
    async def test_render_kpi_cards(self, mock_doc, mock_session):
        """Test rendering KPI cards as table."""
        from app.services.docx_generator import _render_kpi_cards

        block = MagicMock()
        fields = {
            "items": [
                {"label": "Revenue", "value": "100", "unit": "M"},
                {"label": "Profit", "value": "20", "unit": "M"},
            ]
        }

        await _render_kpi_cards(mock_doc, block, fields, {}, "ru", mock_session)

        mock_doc.add_table.assert_called()

    @pytest.mark.asyncio
    async def test_render_kpi_cards_empty(self, mock_doc, mock_session):
        """Test rendering empty KPI cards."""
        from app.services.docx_generator import _render_kpi_cards

        block = MagicMock()
        fields = {"items": []}

        await _render_kpi_cards(mock_doc, block, fields, {}, "ru", mock_session)

        mock_doc.add_table.assert_not_called()

    @pytest.mark.asyncio
    async def test_render_table_builder_cells_column_labels(self, mock_doc, mock_session):
        """TABLE should render Builder mode: data.rows[].cells + fields.column_labels."""
        from app.services.docx_generator import _render_table

        class _Cell:
            def __init__(self):
                self.text = ""
                p = MagicMock()
                p.runs = []
                self.paragraphs = [p]

        class _Row:
            def __init__(self, cols: int):
                self.cells = [_Cell() for _ in range(cols)]

        class _Table:
            def __init__(self, rows: int, cols: int):
                self.rows = [_Row(cols) for _ in range(rows)]
                self.style = None

        # Header + 2 rows
        table = _Table(rows=3, cols=2)
        mock_doc.add_table.return_value = table

        block = MagicMock()
        data = {
            "mode": "builder",
            "columns": [{"key": "a"}, {"key": "b"}],
            "rows": [
                {"cells": {"a": "1", "b": "2"}},
                {"cells": {"a": "3", "b": "4"}},
            ],
        }
        fields = {
            "caption": "Test Table",
            "column_labels": {"a": "A", "b": "B"},
        }

        await _render_table(mock_doc, block, fields, data, "ru", mock_session)

        mock_doc.add_table.assert_called_with(rows=3, cols=2)
        assert table.rows[0].cells[0].text == "A"
        assert table.rows[0].cells[1].text == "B"
        assert table.rows[1].cells[0].text == "1"
        assert table.rows[1].cells[1].text == "2"
        assert table.rows[2].cells[0].text == "3"
        assert table.rows[2].cells[1].text == "4"

    @pytest.mark.asyncio
    async def test_render_table_builder_cells_fields_columns_header(self, mock_doc, mock_session):
        """TABLE should render headers from fields.columns[key].header when column_labels is absent."""
        from app.services.docx_generator import _render_table

        class _Cell:
            def __init__(self):
                self.text = ""
                p = MagicMock()
                p.runs = []
                self.paragraphs = [p]

        class _Row:
            def __init__(self, cols: int):
                self.cells = [_Cell() for _ in range(cols)]

        class _Table:
            def __init__(self, rows: int, cols: int):
                self.rows = [_Row(cols) for _ in range(rows)]
                self.style = None

        table = _Table(rows=2, cols=2)  # header + 1 row
        mock_doc.add_table.return_value = table

        block = MagicMock()
        data = {
            "mode": "builder",
            "columns": [{"key": "col1"}, {"key": "col2"}],
            "rows": [{"cells": {"col1": "2015", "col2": "11200"}}],
        }
        fields = {
            "caption": "Test Table",
            "columns": {
                "col1": {"header": "Year"},
                "col2": {"header": "Headcount"},
            },
        }

        await _render_table(mock_doc, block, fields, data, "en", mock_session)

        assert table.rows[0].cells[0].text == "Year"
        assert table.rows[0].cells[1].text == "Headcount"
        assert table.rows[1].cells[0].text == "2015"
        assert table.rows[1].cells[1].text == "11200"

    @pytest.mark.asyncio
    async def test_render_table_legacy_matrix_header_row_data_rows(self, mock_doc, mock_session):
        """TABLE should render legacy matrix: fields.header_row + fields.data_rows."""
        from app.services.docx_generator import _render_table

        class _Cell:
            def __init__(self):
                self.text = ""
                p = MagicMock()
                p.runs = []
                self.paragraphs = [p]

        class _Row:
            def __init__(self, cols: int):
                self.cells = [_Cell() for _ in range(cols)]

        class _Table:
            def __init__(self, rows: int, cols: int):
                self.rows = [_Row(cols) for _ in range(rows)]
                self.style = None

        table = _Table(rows=3, cols=2)  # header + 2 rows
        mock_doc.add_table.return_value = table

        block = MagicMock()
        data = {
            "mode": "builder",
            "has_header": True,
            "columns": [{"key": "indicator"}, {"key": "y2024"}],
            # IMPORTANT: no data.rows here (real legacy tables can store rows in fields_json)
        }
        fields = {
            "caption": "Legacy Table",
            "header_row": ["Metric", "2024"],
            "data_rows": [
                ["CO2", "100"],
                ["CH4", "50"],
            ],
        }

        await _render_table(mock_doc, block, fields, data, "en", mock_session)

        assert table.rows[0].cells[0].text == "Metric"
        assert table.rows[0].cells[1].text == "2024"
        assert table.rows[1].cells[0].text == "CO2"
        assert table.rows[1].cells[1].text == "100"
        assert table.rows[2].cells[0].text == "CH4"
        assert table.rows[2].cells[1].text == "50"

    @pytest.mark.asyncio
    async def test_render_image_embeds_picture_from_asset_map(self, mock_doc):
        """IMAGE should embed bytes when asset_map (ZIP) is provided."""
        from app.services.docx_generator import _render_image

        asset_id = str(uuid4())
        image_bytes = b"fake-image-bytes"

        block = MagicMock()
        fields = {"alt_text": "Alt", "caption": "Caption"}
        data = {"asset_id": asset_id}

        asset_map = {asset_id: image_bytes}

        await _render_image(mock_doc, block, fields, data, "ru", asset_map)

        mock_doc.add_picture.assert_called_once()
        args, kwargs = mock_doc.add_picture.call_args
        assert len(args) >= 1
        assert isinstance(args[0], io.BytesIO)
        assert args[0].getvalue() == image_bytes

    @pytest.mark.asyncio
    async def test_render_image_falls_back_to_placeholder_when_missing(self, mock_doc):
        """IMAGE should fall back to placeholder when bytes are missing."""
        from app.services.docx_generator import _render_image

        asset_id = str(uuid4())
        block = MagicMock()
        fields = {"alt_text": "Alt"}
        data = {"asset_id": asset_id}

        await _render_image(mock_doc, block, fields, data, "ru", {})

        mock_doc.add_picture.assert_not_called()
        mock_doc.add_paragraph.assert_called()

    @pytest.mark.asyncio
    async def test_render_quote(self, mock_doc, mock_session):
        """Test rendering quote block."""
        from app.services.docx_generator import _render_quote

        block = MagicMock()
        fields = {
            "text": "This is a quote",
            "author": "John Doe",
            "title": "CEO",
        }

        await _render_quote(mock_doc, block, fields, {}, "ru", mock_session)

        # Should add quote text and attribution
        assert mock_doc.add_paragraph.call_count >= 2

    @pytest.mark.asyncio
    async def test_render_downloads(self, mock_doc, mock_session):
        """Test rendering downloads block."""
        from app.services.docx_generator import _render_downloads

        block = MagicMock()
        fields = {
            "items": [
                {"name": "Report.pdf", "description": "Annual report"},
                {"name": "Data.xlsx", "description": "Raw data"},
            ]
        }

        await _render_downloads(mock_doc, block, fields, {}, "ru", mock_session)

        # Heading + 2 list items
        mock_doc.add_paragraph.assert_called()

    @pytest.mark.asyncio
    async def test_render_accordion(self, mock_doc, mock_session):
        """Test rendering accordion (expanded)."""
        from app.services.docx_generator import _render_accordion

        block = MagicMock()
        fields = {
            "items": [
                {"title": "Section 1", "content": "<p>Content 1</p>"},
                {"title": "Section 2", "content": "<p>Content 2</p>"},
            ]
        }

        await _render_accordion(mock_doc, block, fields, {}, "ru", mock_session)

        # Should add headings for each item
        assert mock_doc.add_heading.call_count >= 2

    @pytest.mark.asyncio
    async def test_render_timeline(self, mock_doc, mock_session):
        """Test rendering timeline as table."""
        from app.services.docx_generator import _render_timeline

        # Setup mock table
        mock_table = MagicMock()
        mock_row = MagicMock()
        mock_cell = MagicMock()
        mock_cell.paragraphs = [MagicMock()]
        mock_cell.paragraphs[0].runs = []
        mock_row.cells = [mock_cell, mock_cell, mock_cell]
        mock_table.rows = [mock_row, mock_row, mock_row]
        mock_doc.add_table.return_value = mock_table

        block = MagicMock()
        fields = {
            "events": [
                {"date": "2024-01", "title": "Event 1", "description": "Desc 1"},
                {"date": "2024-06", "title": "Event 2", "description": "Desc 2"},
            ]
        }

        await _render_timeline(mock_doc, block, fields, {}, "ru", mock_session)

        mock_doc.add_table.assert_called()

    @pytest.mark.asyncio
    async def test_render_timeline_new_format_merges_data_and_i18n(self, mock_doc, mock_session):
        """TIMELINE should support new format: data.events + fields.events dict keyed by event_id."""
        from app.services.docx_generator import _render_timeline

        class _Cell:
            def __init__(self):
                self.text = ""
                p = MagicMock()
                p.runs = []
                self.paragraphs = [p]

        class _Row:
            def __init__(self, cols: int):
                self.cells = [_Cell() for _ in range(cols)]

        class _Table:
            def __init__(self, rows: int, cols: int):
                self.rows = [_Row(cols) for _ in range(rows)]
                self.style = None

        # 2 events + header
        table = _Table(rows=3, cols=3)
        mock_doc.add_table.return_value = table

        block = MagicMock()
        fields = {
            "events": {
                "evt-1": {"title": "Event 1", "description": "Desc 1"},
                "evt-2": {"title": "Event 2", "description": "Desc 2"},
            }
        }
        data = {
            "events": [
                {"event_id": "evt-1", "date_start": "2024-01"},
                {"event_id": "evt-2", "date_start": "2024-06"},
            ]
        }

        await _render_timeline(mock_doc, block, fields, data, "ru", mock_session)

        assert table.rows[1].cells[0].text == "2024-01"
        assert table.rows[1].cells[1].text == "Event 1"
        assert table.rows[1].cells[2].text == "Desc 1"
        assert table.rows[2].cells[0].text == "2024-06"
        assert table.rows[2].cells[1].text == "Event 2"
        assert table.rows[2].cells[2].text == "Desc 2"

    @pytest.mark.asyncio
    async def test_chart_to_png_uses_vegalite_to_png(self):
        """Chart conversion must call vegalite_to_png (we generate Vega-Lite specs)."""
        from app.services.docx_generator import _chart_to_png

        fake_vlc = types.SimpleNamespace(
            vegalite_to_png=MagicMock(return_value=b"png-bytes"),
            vega_to_png=MagicMock(return_value=b"wrong"),
        )

        with patch.dict(sys.modules, {"vl_convert": fake_vlc}):
            with patch("app.services.vega_converter.chart_data_to_vega_lite", return_value={"mark": "bar"}):
                out = await _chart_to_png(data={}, fields={})

        assert out == b"png-bytes"
        fake_vlc.vegalite_to_png.assert_called_once()
        fake_vlc.vega_to_png.assert_not_called()

    @pytest.mark.asyncio
    async def test_render_custom_strip_html(self, mock_doc, mock_session):
        """Test rendering custom block strips HTML."""
        from app.services.docx_generator import _render_custom

        block = MagicMock()
        fields = {
            "custom_html": "<div class='custom'><p>Custom content</p></div>"
        }

        await _render_custom(mock_doc, block, fields, {}, "ru", mock_session)

        mock_doc.add_paragraph.assert_called()


class TestBlockRenderersMapping:
    """Tests for block renderers mapping."""

    def test_all_block_types_have_renderer(self):
        """Test all BlockType enum values have a renderer."""
        from app.services.docx_generator import BLOCK_RENDERERS

        for block_type in BlockType:
            assert block_type in BLOCK_RENDERERS, f"Missing renderer for {block_type}"

    def test_renderer_count(self):
        """Test correct number of renderers."""
        from app.services.docx_generator import BLOCK_RENDERERS

        assert len(BLOCK_RENDERERS) == 11


class TestDOCXGeneratorError:
    """Tests for DOCXGeneratorError exception."""

    def test_error_message(self):
        """Test error message stored correctly."""
        from app.services.docx_generator import DOCXGeneratorError

        error = DOCXGeneratorError("Test error message")
        assert str(error) == "Test error message"

    def test_error_is_exception(self):
        """Test DOCXGeneratorError is an Exception."""
        from app.services.docx_generator import DOCXGeneratorError

        assert issubclass(DOCXGeneratorError, Exception)


class TestCoverPage:
    """Tests for cover page generation."""

    def test_add_cover_page(self):
        """Test cover page adds title and year."""
        from app.services.docx_generator import _add_cover_page

        mock_doc = MagicMock()
        mock_doc.add_paragraph = MagicMock(return_value=MagicMock())
        mock_doc.add_page_break = MagicMock()

        mock_report = MagicMock()
        mock_report.title = "Test Report"
        mock_report.year = 2024
        mock_report.company = MagicMock()
        mock_report.company.name = "Test Company"

        _add_cover_page(mock_doc, mock_report, "en")

        mock_doc.add_page_break.assert_called_once()

    def test_add_cover_page_no_company(self):
        """Test cover page without company."""
        from app.services.docx_generator import _add_cover_page

        mock_doc = MagicMock()
        mock_doc.add_paragraph = MagicMock(return_value=MagicMock())
        mock_doc.add_page_break = MagicMock()

        mock_report = MagicMock()
        mock_report.title = "Test Report"
        mock_report.year = 2024
        mock_report.company = None

        _add_cover_page(mock_doc, mock_report, "en")

        mock_doc.add_page_break.assert_called_once()


class TestTOC:
    """Tests for table of contents generation."""

    def test_toc_placeholder_ru(self):
        """TOC placeholder uses a stable English title for any locale."""
        from app.services.docx_generator import _add_toc_placeholder

        mock_doc = MagicMock()
        mock_doc.add_heading = MagicMock()
        mock_doc.add_paragraph = MagicMock(return_value=MagicMock())
        mock_doc.add_page_break = MagicMock()

        _add_toc_placeholder(mock_doc, "ru")

        mock_doc.add_heading.assert_called_with("Contents", level=1)

    def test_toc_placeholder_en(self):
        """Test TOC placeholder in English."""
        from app.services.docx_generator import _add_toc_placeholder

        mock_doc = MagicMock()
        mock_doc.add_heading = MagicMock()
        mock_doc.add_paragraph = MagicMock(return_value=MagicMock())
        mock_doc.add_page_break = MagicMock()

        _add_toc_placeholder(mock_doc, "en")

        mock_doc.add_heading.assert_called_with("Contents", level=1)

    def test_toc_placeholder_kk(self):
        """TOC placeholder uses a stable English title for any locale."""
        from app.services.docx_generator import _add_toc_placeholder

        mock_doc = MagicMock()
        mock_doc.add_heading = MagicMock()
        mock_doc.add_paragraph = MagicMock(return_value=MagicMock())
        mock_doc.add_page_break = MagicMock()

        _add_toc_placeholder(mock_doc, "kk")

        mock_doc.add_heading.assert_called_with("Contents", level=1)
